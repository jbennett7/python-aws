from boto3 import client
from time import sleep
from jinja2 import Template
import json

VPC_ID="vpc-0438aaee9ab9f4c25"
SUBNET_ID="subnet-0eb4bad3b692c74ef"
EKS_ASSUME_ROLE_POLICY_DOCUMENT_PATH="policies/eks_assume.json"

CONTROL_PLANE_INGRESS="sg_policies/control_plane_ingress.json.j2"
WORKER_NODE_INGRESS="sg_policies/worker_node_ingress.json.j2"
BASTION_HOST_INGRESS="sg_policies/bastion_host_ingress.json.j2"
ALB_INGRESS="sg_policies/alb_ingress.json.j2"

def sleep1(): sleep(.25)
def sleep2(): sleep(1)
def iam(): return client('iam')
def ec2(): return client('ec2')
def eks(): return client('eks')

class AWSEks(object):
    def __init__(self, vpc_id):
        self.objs = {}
        self.objs['vpc'] = vpc_id

    def _append_to_objs(self, key, value):
        try:
            self.objs[key].append(value)
        except KeyError:
            self.objs[key] = []
            self.objs[key].append(value)

    def _get_security_groups(self):
        sgs = ec2().describe_security_groups(
                GroupIds=self.objs['sg'])['SecurityGroups']
        control_sg_id = next(sg['GroupId'] for sg in sgs \
            if sg['GroupName'] == 'EKSControlPlaneSecurityGroup')
        worker_sg_id = next(sg['GroupId'] for sg in sgs \
            if sg['GroupName'] == 'EKSWorkerNodeSecurityGroup')
        bastion_sg_id = next(sg['GroupId'] for sg in sgs \
            if sg['GroupName'] == 'EKSBastionHostSecurityGroup')
        alb_sg_id = next(sg['GroupId'] for sg in sgs \
            if sg['GroupName'] == 'EKSApplicationLoadBalancerSecurityGroup')
        return control_sg_id, worker_sg_id, bastion_sg_id, alb_sg_id

    def create_eks_role(self):
        role_name = 'EKSRole'
        pfile = open(EKS_ASSUME_ROLE_POLICY_DOCUMENT_PATH)
        assume_role_policy_document = pfile.read().replace("\n", " ")
        pfile.close()
        try:
            iam().create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=assume_role_policy_document)
            for policy in [ 'AmazonEKSClusterPolicy', 'AmazonEKSServicePolicy']:
                iam().attach_role_policy(
                    RoleName=role_name,
                    PolicyArn="arn:aws:iam::aws:policy/{}".format(policy))
        except iam().exceptions.EntityAlreadyExistsException as e:
            iam().get_role(
                RoleName=role_name)
        self.objs['role'] = role_name

    def create_security_groups(self):
        vpc_id = self.objs['vpc']
        control_sg_id = ec2().create_security_group(
            Description="EKSControlPlaneSecurityGroup",
            GroupName="EKSControlPlaneSecurityGroup",
            VpcId=vpc_id)['GroupId']
        worker_sg_id = ec2().create_security_group(
            Description="EKSWorkerNodeSecurityGroup",
            GroupName="EKSWorkerNodeSecurityGroup",
            VpcId=vpc_id)['GroupId']
        bastion_sg_id = ec2().create_security_group(
            Description='EKSBastionHostSecurityGroup',
            GroupName='EKSBastionHostSecurityGroup',
            VpcId=vpc_id)['GroupId']
        alb_sg_id = ec2().create_security_group(
            Description='EKSApplicationLoadBalancer',
            GroupName='EKSApplicationLoadBalancerSecurityGroup',
            VpcId=vpc_id)['GroupId']
        for sg in [control_sg_id, worker_sg_id, bastion_sg_id, alb_sg_id]:
            self._append_to_objs('sg', sg)

    def authorize_security_group_policies(self):
        control_sg_id, worker_sg_id, bastion_sg_id, alb_sg_id = self._get_security_groups()
        for sg in [(control_sg_id, CONTROL_PLANE_INGRESS), (worker_sg_id, WORKER_NODE_INGRESS),
            (bastion_sg_id, BASTION_HOST_INGRESS), (alb_sg_id, ALB_INGRESS)]:
                with open(sg[1]) as f:
                    data = f.read()
                ec2().authorize_security_group_ingress(
                    GroupId=sg[0],
                    IpPermissions=json.loads(Template(data).render(
                        bastion_sg_id=bastion_sg_id,
                        worker_sg_id=worker_sg_id,
                        control_sg_id=control_sg_id,
                        alb_sg_id=alb_sg_id)))

    def revoke_security_group_policies(self):
        control_sg_id, worker_sg_id, bastion_sg_id, alb_sg_id = self._get_security_groups()
        for sg in [(control_sg_id, CONTROL_PLANE_INGRESS), (worker_sg_id, WORKER_NODE_INGRESS),
            (bastion_sg_id, BASTION_HOST_INGRESS), (alb_sg_id, ALB_INGRESS)]:
                with open(sg[1]) as f:
                    data = f.read()
                ec2().revoke_security_group_ingress(
                    GroupId=sg[0],
                    IpPermissions=json.loads(Template(data).render(
                        bastion_sg_id=bastion_sg_id,
                        worker_sg_id=worker_sg_id,
                        control_sg_id=control_sg_id,
                        alb_sg_id=alb_sg_id)))

    def delete_security_groups(self):
        for sg in self.objs['sg']:
            ec2().delete_security_group(GroupId=sg)
        del(self.objs['sg'])

    def delete_eks_role(self):
        for policy in [ 'AmazonEKSClusterPolicy', 'AmazonEKSServicePolicy']:
            iam().detach_role_policy(
                RoleName=self.objs['role'],
                PolicyArn="arn:aws:iam::aws:policy/{}".format(policy))
        iam().delete_role(RoleName=self.objs['role'])
        del(self.objs['role'])

if __name__ == '__main__':
    eks = AWSEks(vpc_id=VPC_ID)
    eks.create_eks_role()
    eks.create_security_groups()
    eks.authorize_security_group_policies()
    eks.revoke_security_group_policies()
    print(eks.objs)
    eks.delete_security_groups()
    eks.delete_eks_role()
    print(eks.objs)
