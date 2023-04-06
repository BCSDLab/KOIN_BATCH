package main

import (
	"bufio"
	"context"
	"database/sql"
	"fmt"
	"go.mongodb.org/mongo-driver/bson"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
	"gopkg.in/yaml.v3"
)

type BusInfo struct {
	region  string
	busType string
}

var fileMapper = map[string]BusInfo{
	"cheonan_commuting.yaml":  {region: "천안", busType: "commuting"},
	"cheonan_shuttle.yaml":    {region: "천안", busType: "shuttle"},
	"sejong_commuting.yaml":   {region: "세종", busType: "commuting"},
	"daejeon_commuting.yaml":  {region: "대전", busType: "commuting"},
	"seoul_commuting.yaml":    {region: "서울", busType: "commuting"},
	"cheongju_shuttle.yaml":   {region: "청주", busType: "shuttle"},
	"cheongju_commuting.yaml": {region: "청주", busType: "commuting"},
}

type Timetable struct {
	ToSchool   []Route `yaml:"to_school" json:"to_school" bson:"to_school"`
	FromSchool []Route `yaml:"from_school" json:"from_school" bson:"from_school"`
}

type SchoolBus struct {
	Region    string  `yaml:"region" json:"region" bson:"region"`
	BusType   string  `yaml:"bus_type" json:"bus_type" bson:"bus_type"`
	Direction string  `yaml:"direction" json:"direction" bson:"direction"`
	Routes    []Route `yaml:"routes" json:"routes" bson:"routes"`
}

type Route struct {
	RouteName   string        `yaml:"route_name" json:"route_name" bson:"route_name"`
	RunningDays []string      `yaml:"running_days" json:"running_days" bson:"running_days"`
	ArrivalInfo []ArrivalInfo `yaml:"arrival_info" json:"arrival_info" bson:"arrival_info"`
}

type ArrivalInfo struct {
	NodeName    string `yaml:"node_name" json:"node_name" bson:"node_name"`
	ArrivalTime string `yaml:"arrival_time" json:"arrival_time" bson:"arrival_time"`
}

func bindingData(data []byte, class interface{}) error {
	switch class.(type) {
	case *Timetable:
		err := yaml.Unmarshal(data, class)
		if err != nil {
			return fmt.Errorf("error on binding: %w", err)
		}
	}
	return nil
}

func getBusSchedule(fileName string, class interface{}) error {
	data, err := os.ReadFile(fileName)
	if err != nil {
		return fmt.Errorf("error on reading: %w", err)
	}
	return bindingData(data, class)
}

type Properties map[string]string

func ConnectDB(configs Properties) (client *mongo.Client, ctx context.Context, cancel context.CancelFunc) {
	ctx, cancel = context.WithTimeout(context.Background(), 3*time.Second)

	uri := fmt.Sprintf("%s://%s:%s", "mongodb", configs["mongo.host"], configs["mongo.port"])

	clientOptions := options.Client().ApplyURI(uri)
	client, _ = mongo.Connect(ctx, clientOptions)

	return client, ctx, cancel
}

func getConfigProperties() (Properties, error) {
	configFile, err := os.Open("config.properties")
	if err != nil {
		panic(err.Error())
	}

	configs := Properties{}
	properties, err := fillConfigProperties(configFile, configs, err)

	if err != nil {
		return properties, err
	}
	return configs, nil
}

func fillConfigProperties(configFile *os.File, configs Properties, err error) (Properties, error) {
	scanner := bufio.NewScanner(configFile)
	for scanner.Scan() {
		aLine := scanner.Text()

		separateIndex := strings.Index(aLine, "=")
		if separateIndex == -1 {
			continue
		}

		key := strings.TrimSpace(aLine[:separateIndex])
		value := strings.TrimSpace(aLine[separateIndex+1:])

		if len(key) == 0 {
			continue
		}
		configs[key] = value
	}

	err = scanner.Err()
	if err != nil {
		return nil, err
	}

	return nil, nil
}

func main() {
	//Config
	configs, err := getConfigProperties()

	if err != nil {
		panic(err.Error())
	}

	// MongoDB
	mongodb, ctx, _ := ConnectDB(configs)
	col := mongodb.Database(configs["mongo.database"]).Collection("bus_timetables")
	findAndReplaceOptions := options.FindOneAndReplaceOptions{}
	findAndReplaceOptions.SetUpsert(true)

	// MySQL
	dataSourceName := fmt.Sprintf("%s:%s@%s(%s:%s)/%s", configs["dataSource.username"], configs["dataSource.password"], configs["dataSource.protocol"], configs["dataSource.ipAddress"], configs["dataSource.port"], configs["dataSource.database"])
	mysql, err := sql.Open(configs["dataSource.driverName"], dataSourceName)
	if err != nil {
		panic(err.Error())
	}
	defer func(mysql *sql.DB) {
		err := mysql.Close()
		if err != nil {
			panic(err.Error())
		}
	}(mysql)

	_, filename, _, _ := runtime.Caller(0)
	pwd := filepath.Dir(filename)

	// 통학버스
	for key, value := range fileMapper {
		schoolBus := new(Timetable)
		if err := getBusSchedule(filepath.Join(pwd, key), schoolBus); err != nil {
			log.Fatal(err)
		}

		schoolBusTo, schoolBusFrom := &SchoolBus{
			Region:    value.region,
			BusType:   value.busType,
			Direction: "to",
			Routes:    schoolBus.ToSchool,
		}, &SchoolBus{
			Region:    value.region,
			BusType:   value.busType,
			Direction: "from",
			Routes:    schoolBus.FromSchool,
		}

		if err := col.FindOneAndReplace(ctx, bson.D{
			{"region", schoolBusTo.Region},
			{"bus_type", schoolBusTo.BusType},
			{"direction", schoolBusTo.Direction},
		}, schoolBusTo, &findAndReplaceOptions); err.Err() != nil {
			log.Printf("%s-%s-%s 저장 완료\r\n", schoolBusTo.BusType, schoolBusTo.Region, schoolBusTo.Direction)
		} else {
			log.Printf("%s-%s-%s 업데이트 완료\r\n", schoolBusTo.BusType, schoolBusTo.Region, schoolBusTo.Direction)
		}

		if err := col.FindOneAndReplace(ctx, bson.D{
			{"region", schoolBusFrom.Region},
			{"bus_type", schoolBusFrom.BusType},
			{"direction", schoolBusFrom.Direction},
		}, schoolBusFrom, &findAndReplaceOptions); err.Err() != nil {
			log.Printf("%s-%s-%s 저장 완료\r\n", schoolBusFrom.BusType, schoolBusFrom.Region, schoolBusFrom.Direction)
		} else {
			log.Printf("%s-%s-%s 업데이트 완료\r\n", schoolBusFrom.BusType, schoolBusFrom.Region, schoolBusFrom.Direction)
		}
	}

	updateVersion(mysql)
}

func updateVersion(mysql *sql.DB) {
	now := time.Now()
	version := fmt.Sprintf("%d_%d", now.Year(), now.UnixMilli())
	if _, err := mysql.Query(
		"INSERT INTO versions (version, type) VALUES (?, ?) ON DUPLICATE KEY UPDATE version = ?;",
		version,
		"bus_timetable",
		version,
	); err == nil {
		log.Printf("%s 버전 업데이트 완료\r\n", version)
	} else {
		log.Fatal("버전 업데이트 실패\r\n", err)
	}
}
