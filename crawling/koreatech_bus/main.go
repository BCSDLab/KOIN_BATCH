package main

import (
	"context"
	"fmt"
	"go.mongodb.org/mongo-driver/bson"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"time"

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
	ToSchool   []Course `yaml:"to_school" json:"to_school" bson:"to_school"`
	FromSchool []Course `yaml:"from_school" json:"from_school" bson:"from_school"`
}

type SchoolBus struct {
	Region    string   `yaml:"region" json:"region" bson:"region"`
	BusType   string   `yaml:"bus_type" json:"bus_type" bson:"bus_type"`
	Direction string   `yaml:"direction" json:"direction" bson:"direction"`
	Courses   []Course `yaml:"courses" json:"courses" bson:"courses"`
}

type Course struct {
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

func ConnectDB() (client *mongo.Client, ctx context.Context, cancel context.CancelFunc) {
	ctx, cancel = context.WithTimeout(context.Background(), 3*time.Second)
	clientOptions := options.Client().ApplyURI("mongodb://" + "localhost:27017")
	client, _ = mongo.Connect(ctx, clientOptions)
	return client, ctx, cancel
}

func main() {
	client, ctx, _ := ConnectDB()
	col := client.Database("koin").Collection("bus_timetables")
	findAndReplaceOptions := options.FindOneAndReplaceOptions{}
	findAndReplaceOptions.SetUpsert(true)

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
			Courses:   schoolBus.ToSchool,
		}, &SchoolBus{
			Region:    value.region,
			BusType:   value.busType,
			Direction: "from",
			Courses:   schoolBus.FromSchool,
		}

		if err := col.FindOneAndReplace(ctx, bson.D{
			{"region", schoolBusTo.Region},
			{"bus_type", schoolBusTo.BusType},
			{"direction", schoolBusTo.Direction},
		}, schoolBusTo, &findAndReplaceOptions); err.Err() != nil {
			log.Printf("%s-%s-%s 저장 완료\n", schoolBusTo.BusType, schoolBusTo.Region, schoolBusTo.Direction)
		} else {
			log.Printf("%s-%s-%s 업데이트 완료\n", schoolBusTo.BusType, schoolBusTo.Region, schoolBusTo.Direction)
		}

		if err := col.FindOneAndReplace(ctx, bson.D{
			{"region", schoolBusFrom.Region},
			{"bus_type", schoolBusFrom.BusType},
			{"direction", schoolBusFrom.Direction},
		}, schoolBusFrom, &findAndReplaceOptions); err.Err() != nil {
			log.Printf("%s-%s-%s 저장 완료\n", schoolBusFrom.BusType, schoolBusFrom.Region, schoolBusFrom.Direction)
		} else {
			log.Printf("%s-%s-%s 업데이트 완료\n", schoolBusFrom.BusType, schoolBusFrom.Region, schoolBusFrom.Direction)
		}
	}
}
