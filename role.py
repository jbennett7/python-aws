from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))
from utility import iam, eks, ec2

from jinja2 import Template
import json
import yaml

class IamRole(object):
    def __init__(self, obj_list=None):
        if path is not None
            with open(path) as f:
                data = f.read()
            self.objs = yaml.load(data)
        else:
            self.objs = {}

    def _append_to_objs(self, key, value):
        try:
            self.objs[key].append(value)
        except KeyError:
            self.objs[key] = []
            self.objs[key].append(value)

    def create_role( self,
                     role_name,
                     assume_policy_document_path,
                     policy_attachments):
        pfile = open(assume_policy_document_path)
        assume_role_policy_document = pfile.read().replace("\n", " ")
        pfile.close()
        try:
            iam().create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=assume_role_policy_document)
            for policy in policy_attachments:
                iam().attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/{}".format(policy))
        except iam().exceptions.EntityAlreadyExistsException as e:
            iam().get_role(
                RoleName=role_name)
        self._append_to_objs('role', role_name)

    def delete_role(self, role_name):
        policy_list = [ arn for arn in \
            iam().list_attached_role_policies(RoleName=role_name)['AttachedPolicies'] ]
        for policy in policy_list:
            iam().detach_role_policy(
                RoleName=self.objs['role'],
                PolicyArn=policy)
        iam().delete_role(RoleName=role_name)
        self.objs['role'].remove(role_name)
        
