import yaml
from boto3 import client
from time import sleep

def sleep1(): sleep(.1)
def sleep2(): sleep(.25)
def sleep3(): sleep(5)

def ec2(): return client('ec2')
def eks(): return  client('eks')
def iam(): return client('iam')
