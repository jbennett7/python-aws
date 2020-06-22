from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))

import re
from utility import ec2
from boto3 import client
from time import sleep
from botocore.exceptions import ClientError
import yaml

class Waiter(Exception):
    def __init__(self, seconds=.1):
        sleep(seconds)

class AwsBase(dict):
    def __init__(self, path):
        self.path = path
        self.load()

#   def __str__(self):
#       return super(AwsObjectDict, self).__str__()
#       return super().__str__()

#   def __repr__(self):
#       yaml.representer(AwsObjectDict, lambda self, 
#       return super().__repr__()

#   def __iter__(self):
#       for key in self.keys():
#           yield (key, self[key])

#   def __setitem__(self, key, value):
#       super().__setitem__(key, value)
 
#   def __delitem__(self, key):
#       super().__delitem__(key)
 
#   def __getitem__(self, key):
#       return super().__getitem__(key)
#
#   def __str__(self):
#       return super().__str__()
#
#   def __hash__(self):
#       return super().objs.__hash__()
#
    def tag_resources(self, resource_ids, tags):
        r = ec2().create_tags(Resources=resource_ids, Tags=tags)
        print(r)

    def execute(self, cmd):
        res = cmd
        k = next(k for k in list(res.keys()) if k != 'ResponseMetadata')
        try:
            del(res[k]['State'])
        except KeyError:
            pass
        return k, res[k]

    def waiter(self, cmd, k):
        w = 1
        while True:
            s = .1 * w if w < 50 else 5
            w = 2 * w + 1 if w < 50 else 50
            try:
                res = cmd
                w, m = res
                if res[w][0]['State'] != 'available':
                    sleep(s)
                    continue
            except ClientError as c:
                if re.match( r'.*\.NotFound', c.response['Error']['Code']):
                    continue
            except KeyError as e:
                break
            break

    def append_to_objs(self, key, value):
        try:
            self[key].append(value)
        except KeyError:
            self[key] = []
            self[key].append(value)

    def save(self):
        with open(self.path, 'w') as f:
            yaml.safe_dump(dict(self), f, default_flow_style=False)

    def load(self):
        try:
            data = yaml.load(open(self.path).read())
            for key in data.keys(): self[key] = data[key]
        except FileNotFoundError:
            self = {}

    def remove(self, key, value=None):
        if value is None:
            del(self[key])
            return 0
        if isinstance(self[key], list):
            self[key].remove(value)
