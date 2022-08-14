package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"time"

	"github.com/go-redis/redis/v8"
	"gopkg.in/yaml.v3"
)

const RedisKey = "Tago@busTimetable.%s.%s"

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

type ExpressBus struct {
	TerminalToKoreatech []ExpressBusTime `yaml:"terminal_to_koreatech" json:"terminal_to_koreatech"`
	KoreatechToTerminal []ExpressBusTime `yaml:"koreatech_to_terminal" json:"koreatech_to_terminal"`
}

type ExpressBusTime struct {
	Departure string `yaml:"departure" json:"departure"`
	Arrival   string `yaml:"arrival" json:"arrival"`
}

type SchoolBus struct {
	ToSchool   []Course `yaml:"to_school" json:"to_school"`
	FromSchool []Course `yaml:"from_school" json:"from_school"`
}

type Course struct {
	RouteName   string        `yaml:"route_name" json:"route_name"`
	ArrivalInfo []ArrivalInfo `yaml:"arrival_info" json:"arrival_info"`
}

type ArrivalInfo struct {
	NodeName    string `yaml:"node_name" json:"node_name"`
	ArrivalTime string `yaml:"arrival_time" json:"arrival_time"`
}

func bindingData(data []byte, class interface{}) error {
	switch class.(type) {
	case *ExpressBus, *SchoolBus:
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

func main() {
	rdb := redis.NewClient(&redis.Options{
		Addr:     "localhost:6379",
		Username: "",
		Password: "",
		DB:       0,
	})

	// 고속버스
	expressBus := new(ExpressBus)
	if err := getBusSchedule("express_bus.yaml", expressBus); err != nil {
		log.Fatalf("%v\n", err)
	}
	jsonData, err := json.Marshal(expressBus)
	if err != nil {
		log.Fatalf("error on marshaling json: %v\n", err)
	}
	rdb.Set(context.TODO(), fmt.Sprintf(RedisKey, "express", ""), jsonData, time.Duration(0))
	log.Printf("%s 저장완료\n", fmt.Sprintf(RedisKey, "express", ""))

	// 통학버스
	for key, value := range fileMapper {
		shuttleBus := new(SchoolBus)
		if err := getBusSchedule(key, shuttleBus); err != nil {
			log.Fatal(err)
		}
		jsonData, err := json.Marshal(shuttleBus)
		if err != nil {
			log.Fatalf("error on marshaling json: %v", err)
		}
		rdb.Set(context.TODO(), fmt.Sprintf(RedisKey, value.busType, value.region), jsonData, time.Duration(24)*time.Hour)
		log.Printf("%s 저장완료\n", fmt.Sprintf(RedisKey, value.busType, value.region))
	}
}
