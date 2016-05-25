# Zabbix AWS Monitoring Templates

This template collection is for effective monitoring AWS(Amazon Web Services) with Zabbix.

# What templates?

* Amazon CloudWatch Metrics monitoring Template
* AWS Service Health Dashboard monitoring Template (comming soon..)
* AWS EC2 auto scaling monitoring Template (comming soon..)
* Other templates are under considering.

# Requirements

Operation has been confirmed under the following environments.

* CentOS7.2 or Amazon Linux 2016.3
* Python 2.7
* boto3(AWS SDK for Python)
* Zabbix 2.2 or 3.0

# Amazon CloudWatch Metrics monitoring Template
## Architecture

![CloudWatch monitoring architecture](https://github.com/tech-sketch/zabbix_aws_template/wiki/images/cloudwatch_zabbix_arch.png)

## How to use

Only 3 steps.

1. Download and set a python script
2. Import template
3. Register hosts

### Download and set a python script

Please download scripts/cloudwatch_zabbix.py on your Zabbix Server (External Scripts directory).
And please set exec permission to Zabbix Server user(default: zabbix).

### Import template

Please import templates/3.0/cloudwatch_template.xml at Zabbix WebGUI ([Configuration]->[Templates]->Import).
(In case of Zabbix 2.2: templates/2.2/cloudwatch_template.xml)

### Register hosts

Please register Zabbix hosts for EC2 instances, RDS instances, ELB, EBS volume or others.

In case of an EC2 instance:

* Host name: i-xxxxx (please set Instance ID)
* Templates: Template AWS EC2
* Macros:
    * {$REGION} : set AWS region name(e.g. ap-northeast-1)
    * {$KEY} : set AWS Access Key ID (e.g. AKI........)
    * {$SECRET} : set AWS Secret Access Key

#### Tip

If you don't want to set AWS credentials info at Zabbix Macro, please set OS environment variables.

* AWS_DEFAULT_REGION
* AWS_ACCESS_KEY_ID
* AWS_SECRET_ACCESS_KEY

And, please change external check items key.

before:
```
cloudwatch_zabbix.py[ec2,"-r",{$REGION},"-a",{$KEY},"-s",{$SECRET},"-i",{HOST.HOST},"-m","True"]
```

after:
```
cloudwatch_zabbix.py[ec2,"-i",{HOST.HOST},"-m","True"]
```


# AWS Service Health Dashboard monitoring Template

comming soon...

# AWS EC2 AutoScaling monitoring Template

comming soon...

# License

Licensed under the Apache License, Version 2.0.
The Apache v2 full text is published at this link(http://www.apache.org/licenses/LICENSE-2.0).

# Contact

TIS Inc.
OSS Promotion Office
oss@pj.tis.co.jp

---
Copyright 2016 TIS Inc.
