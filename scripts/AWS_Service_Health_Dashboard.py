#!/bin/env python
import re
import argparse
import calendar
import datetime
import dateutil.parser
import feedparser
import threading
import time
import urllib2
import argparse
import json
import socket
import struct
from HTMLParser import HTMLParser

class AWSSHDParser(HTMLParser):


    def __init__(self, base_url, block, zabbix_host, zabbix_port):
        HTMLParser.__init__(self)
        self.block = block
        self.check = False
        self.base_url = base_url
        self.url_list = []
        self.lld_json = json.loads('{"data":[]}')
        self.zabbix_host = zabbix_host
        self.zabbix_port = zabbix_port


    def get_rss(self, url):
        now = "%.9f" % time.time()
        sec = now.split(".")[0]
        ns = now.split(".")[1]
        send_data = json.loads('{"request":"sender data","data":[],"clock":"%s","ns":"%s" }' % (sec, ns))
        response = feedparser.parse(url)
        send_items = []

        for entry in range(len(response.entries)):
            title = response.entries[entry].title
            published = response.entries[entry].published

            pub = dateutil.parser.parse(published)
            uni = calendar.timegm(pub.utctimetuple())
            now = calendar.timegm(time.gmtime())

            if now - args.interval < uni:
                send_json_string = '{"host":"", "key":"", "value":"", "clock":""}'
                send_item = json.loads(send_json_string)
                send_item["host"] = self.block

                replace = re.compile(".+/rss/(.*?)(-(ap-[a-z]+-[0-9]|us-[a-z]+-[0-9]|eu-[a-z]+-[0-9]|sa-[a-z]+-[0-9]))*\.rss")
                match = replace.match(url)
                ServiceName = match.group(1)
                Region = match.group(3)
                
                if Region == None:
                    send_item["key"] = 'health.status[%s.]' % ServiceName
                else:
                    send_item["key"] = 'health.status[%s.%s]' % (ServiceName, Region)

                send_item["value"] = title
                send_item["clock"] = uni
                send_items.append(send_item)
            else:
                break
        send_data["data"].extend(send_items)
        self.__send_to_zabbix(send_data)


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


    def handle_starttag(self, tagname, attribute):
        if tagname.lower() == "div":
            for i in attribute:
                if i[1] == self.block + "_block":
                    self.check = True
        if self.check == True and tagname.lower() == "a":
            for i in attribute:
                if i[0].lower() == "href":
                    self.url_list.append(self.base_url + i[1][1:])
                    lld_json_string = '{"{#SERVICE.NAME}":"", "{#REGION}":""}'
                    lld_item = json.loads(lld_json_string)
                    
                    replace = re.compile(".+/rss/(.*?)(-(ap-[a-z]+-[0-9]|us-[a-z]+-[0-9]|eu-[a-z]+-[0-9]|sa-[a-z]+-[0-9]))*\.rss")
                    match = replace.match(self.base_url + i[1][1:])
                    ServiceName = match.group(1)
                    Region = match.group(3)
                    
                    if Region == None:
                        lld_item["{#SERVICE.NAME}"] = ServiceName
                        lld_item["{#REGION}"] = ""
                    else:
                        lld_item["{#SERVICE.NAME}"] = ServiceName
                        lld_item["{#REGION}"] = Region
                        
                    self.lld_json["data"].append(lld_item)


    def handle_endtag(self, tagname):
        if tagname.lower() == "div":
            self.check = False


if __name__== "__main__":
    parser = argparse.ArgumentParser(description='Get RSS list or Zabbix LLD format output from AWS Service Health Dashboard page.')
    parser.add_argument('-b', '--block', default="AP", help='set AWS region block(e.g.:NA or SA or EU or AP)')
    parser.add_argument('-i', '--interval', type=int, help='set interval time (seconds)')
    parser.add_argument('-m', '--send-mode', default='False', help='set True if you send AWS Service Health Dashboard status information. set False if you want to get lld format service list. (e.g.: True or False)')
    parser.add_argument('-p', '--zabbix-port', type=int, default=10051, help='set listening port number for Zabbix server')
    parser.add_argument('-z', '--zabbix-host', default='localhost', help='set listening IP address for Zabbix server')

    block_list = ["NA", "SA", "EU", "AP"]
    args = parser.parse_args()
    
    if args.block not in block_list:
        print "please set block name. :" + " or ".join(map(str, block_list))

    base_url = "http://status.aws.amazon.com/"
    socket.setdefaulttimeout(30) 
    htmldata = urllib2.urlopen(base_url)
    
    parser = AWSSHDParser(base_url, args.block, args.zabbix_host, args.zabbix_port)
    parser.feed(htmldata.read())

    if args.send_mode.upper() == "TRUE":
        for url in parser.url_list:
            get_rss_th = threading.Thread(target=parser.get_rss,name="get_rss_th", args=(url,))
            get_rss_th.start()

    if args.send_mode.upper() == "FALSE":
        print json.dumps(parser.lld_json)
        
    parser.close()
    htmldata.close()
