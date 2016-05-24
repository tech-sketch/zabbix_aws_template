#!/bin/env python

import boto3
import json
import argparse
import os
import socket
import struct
import time
import calendar
from datetime import datetime
from datetime import timedelta

class Metric:
    def __init__(self, name="", namespace="", unit=""):
        self.name = name
        self.namespace = namespace
        self.unit = unit

class AwsZabbix:

    def __init__(self, region, access_key, secret, identity, service,
                 zabbix_host='localhost', zabbix_port=10051):
        self.zabbix_host = zabbix_host
        self.zabbix_port = zabbix_port
        self.identity = identity
        self.service = service
        self.id_dimentions = {
            'ec2':'InstanceId',
            'rds':'DBInstanceIdentifier',
            'elb':'LoadBalancerName',
            'ebs':'VolumeId',
            'billing': 'Currency'
        }
        self.client = boto3.client(
            'cloudwatch',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret
        )

    def __get_metric_list(self):
        resp = self.client.list_metrics(
            Dimensions = [
                {
                    'Name': self.id_dimentions[self.service],
                    'Value': self.identity
                }
            ]
        )
        metric_list = []
        for data in resp["Metrics"]:
            metric = Metric(name=data["MetricName"], namespace=data["Namespace"])
            if self.service == "elb":
                for dimension in data["Dimensions"]:
                    if dimension["Name"] == "AvailabilityZone":
                       metric.name = data["MetricName"] + "." + dimension["Value"]
            metric_list.append(metric)
        return metric_list

    def __get_metric_stats(self, metric_name, metric_namespace, stat_type="Average", timerange_min=10, period_sec=300):
        dimensions = [
            {
                'Name': self.id_dimentions[self.service],
                'Value': self.identity
            }
        ]
        if self.service == "elb":
            split_metric_name = metric_name.split(".")
            if len(split_metric_name) == 2:
                metric_name = split_metric_name[0]
                dimensions.append(
                    {
                        'Name': 'AvailabilityZone',
                        'Value': split_metric_name[1]
                    }
                )
        stats = self.client.get_metric_statistics(
            Namespace=metric_namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=datetime.utcnow() - timedelta(minutes=timerange_min),
            EndTime=datetime.utcnow(),
            Period=period_sec,
            Statistics=[stat_type],
        )
        return stats

    def __set_unit(self, metric_list):
        ret_val = []
        for metric in metric_list:
            stats = self.__get_metric_stats(metric.name, metric.namespace)
            for datapoint in stats["Datapoints"]:
                metric.unit = datapoint["Unit"]
                break
            ret_val.append(metric)
        return ret_val

    def __get_send_items(self, stats, metric):
        send_items = []
        for datapoint in stats["Datapoints"]:
            send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
            send_item = json.loads(send_json_string)

            send_item["host"] = self.identity
            send_item["key"] = 'cloudwatch.metric[%s]' % metric.name
            send_item["value"] = datapoint["Average"]
            send_item["clock"] = calendar.timegm(datapoint["Timestamp"].utctimetuple())
            send_items.append(send_item)
        return send_items


    def __send_to_zabbix(self, send_data):
        send_data_string = json.dumps(send_data)
        zbx_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            zbx_client.connect((self.zabbix_host, self.zabbix_port))
        except Exception:
            print "Can't connect to zabbix server"
            quit()

        header = struct.pack('<4sBQ', 'ZBXD', 1, len(send_data_string))
        send_data_string = header + send_data_string
        try:
            zbx_client.sendall(send_data_string)
        except Exception:
            print 'Data sending failure'
            quit()
        response = ''
        while True:
            data = zbx_client.recv(4096)
            if not data:
                break
            response += data

        print response[13:]
        zbx_client.close()


    def send_metric_data_to_zabbix(self):
        send_data = json.loads('{"request":"sender data","data":[]}')
        metric_list = self.__get_metric_list()
        all_metric_stats = []
        for metric in metric_list:
            stats = self.__get_metric_stats(metric.name, metric.namespace)
            send_data["data"].extend(self.__get_send_items(stats, metric))
        self.__send_to_zabbix(send_data)

    def show_metriclist_lld(self):
        lld_output_json = json.loads('{"data":[]}')
        metric_list = self.__get_metric_list()
        metric_list = self.__set_unit(metric_list)
        for metric in metric_list:
            lld_json_string = '{"{#METRIC.NAME}":"", "{#METRIC.UNIT}":"", "{#METRIC.NAMESPACE}":""}'
            lld_item = json.loads(lld_json_string)
            lld_item["{#METRIC.NAME}"] = metric.name
            lld_item["{#METRIC.NAMESPACE}"] = metric.namespace
            lld_item["{#METRIC.UNIT}"] = metric.unit
            lld_output_json["data"].append(lld_item)
        print json.dumps(lld_output_json)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get AWS CloudWatch Metric list json format.')

    parser.add_argument('-r', '--region', default=os.getenv("AWS_DEFAULT_REGION"), help='set AWS region name(e.g.: ap-northeast-1)')
    parser.add_argument('-a', '--accesskey', default=os.getenv("AWS_ACCESS_KEY_ID"), help='set AWS Access Key ID')
    parser.add_argument('-s', '--secret', default=os.getenv("AWS_SECRET_ACCESS_KEY"), help='set AWS Secret Access Key')
    parser.add_argument('-i', '--identity', required=True, help='set Identity data (ec2: InstanceId, elb: LoadBalancerName, rds: DBInstanceIdentifier, ebs: VolumeId)')
    parser.add_argument('-m', '--send-mode', default=False, help='set True if you send statistic data (e.g.: True or False)')
    parser.add_argument('service', metavar='service_name', help='set Service name (e.g.: ec2 or elb or rds')

    args = parser.parse_args()

    aws_zabbix = AwsZabbix(region=args.region, access_key=args.accesskey, secret=args.secret, identity=args.identity, service=args.service)

    if args.send_mode:
        aws_zabbix.send_metric_data_to_zabbix()
    else:
        aws_zabbix.show_metriclist_lld()
