import boto3
import botocore
import paramiko
from termcolor import colored 
import time

###################################################################################################################################

#A Python Boto3 script which:
#---------------------------------------------------

#Lists EC2 Instances and associated Volumes..
#Accepts Forensic(compromised) Volume ID & Instance ID selection:
#-------
#Turns off the selected instance
#Detaches the Forensic(compromised) Volume from the selected Instance
#-------
#Lists the LifeCycle Manager Snapshots
#Accepts Snapshot ID selection:  
#Builds new Volume from Snapshot
#-------
#Builds a SIFT Workstation Instance
#-------
#Attaches the Snapshot Volume & Forensic(compromised) Volume to the SIFT Workstation
#-------
#SSH into SIFT Workstation Instance and mounts the Volumes

#################################################################################################################################

#Import AWS creds from config.properties

def getVarFromFile(filename):
    import imp
    f = open(filename)
    global data
    data = imp.load_source('data', '', f)
    f.close()

getVarFromFile('config.properties')

################################################################################################################################

#Set Boto3 Resource and Client variables

vpc_resource = boto3.resource('ec2')
vpc_client = boto3.client('ec2')

#################################################################################################################################

#Lists EC2 Instances and associated Volumes..

print(" \nPRINTING EC2 INSTANCE STATS" )
print('-------------------------------------------------- \n')

for instance in vpc_resource.instances.all():

    for instance_name in instance.tags:
        if instance_name['Key'] == 'Name':
            print_value = instance_name['Value']
            print colored("Instance: %s" %print_value, 'green')
    print(
         "Id: {0}\nPublic IP: {1}\nPrivate IP: {2}\nSubnet: {3}\nAMI: {4}\n".format(
         instance.id, instance.public_ip_address, instance.private_ip_address, instance.subnet_id, instance.image.id
         )
     )

    for vol_data in instance.block_device_mappings:
        volume = vol_data.get('Ebs')
        print(
            "Mounted Vol: {0}\nVol Id: {1}\nVol Status: {2}\n".format(
            vol_data['DeviceName'], volume.get('VolumeId'), volume.get('Status')
            )
        )
    print('--------\n')
print('\n################################################\n')

################################################################################################################################

#Accepts Forensic(compromised) Volume selection:

print("[ ENTER INSTANCE ID & VOLUME ID TO DETACH FORENSIC(compromised) VOLUME ]\n")
selected_instance_id = raw_input("ENTER INSTANCE ID:\n")
selected_volume_id = raw_input("ENTER VOLUME ID:\n")

################################################################################################################################

#Turn off/Shutdown selected Instance

print('\n===> TURNING OFF SELECTED INSTANCE..')
turn_off_instance = vpc_client.stop_instances(
    InstanceIds = [
        selected_instance_id
    ]
)
time.sleep(30)
print('\n===> INSTANCE SHUTDOWN COMPLETE')
print(selected_instance_id)

################################################################################################################################

#Detach the Forensic(compromised) Volume of selected instance

print('\n===> DETACHING SELECTED VOLUME FROM INSTANCE..')
for_vol_detach = vpc_client.detach_volume(
    VolumeId = selected_volume_id
)
time.sleep(10)
print('\n===> VOLUME DETACH COMPLETE')
print(selected_volume_id)

################################################################################################################################

#List the Lifecycle Manager Snapshots of EC2 Instances 

print('\n################################################\n')
snapshot_printer = [{'Name':'tag:Auto_snapshot', 'Values':['True']}]
snapshots = list(vpc_resource.instances.filter(Filters=snapshot_printer))
for instance in snapshots:
    print(
         "\nId: {0}\nPublic IP: {1}\nPrivate IP: {2}\nSubnet ID: {3}\n".format(
         instance.id, instance.public_ip_address, instance.private_ip_address, instance.subnet_id
         )
    )
    volumes = instance.volumes.all()
    for vol in volumes:
        print(
            "Volume Id: {0}\nSnapshot ID: {1}\nCreated at: {2}\nState: {3}\n".format(
            vol.id, vol.snapshot_id, vol.create_time, vol.state
            )
        )

################################################################################################################################

#Accept Snapshot ID selection:  

print('\n################################################\n')
print("[ SELECT SNAPSHOT ID TO CREATE SNAPSHOT VOLUME ]\n")
snapshot_id = raw_input("\nENTER SNAPSHOT ID:\n")

#################################################################################################################################

#Build Snapshot Volume

print('\n===> Building SNAPSHOT VOLUME..\n')
snapshot_vol = vpc_client.create_volume(
    AvailabilityZone = data.availibilityZone_value,
    SnapshotId = snapshot_id
)
time.sleep(20)

for key,value in snapshot_vol.items():
    if key == 'VolumeId':
        snapshot_vol_id = value
print('===> SNAPSHOT VOLUME BUILD COMPLETE\n')
print(snapshot_vol_id)

#################################################################################################################################

#create a new sift workstation 

print('\n===> BUILDING SIFT WORKSTATION INSTANCE..\n')
workstation_instance = vpc_resource.create_instances(
    ImageId = data.ImageId_value,
    SubnetId = data.SubnetId_value,
    MinCount = data.MinCount_value,
    MaxCount = data.MaxCount_value,
    KeyName = data.KeyName_value,
    InstanceType = data.InstanceType_value
)

for instance in workstation_instance:
    instance.wait_until_running()
    instance.reload()
    print('===> SIFT WORKSTATION BUILD COMPLETE\n')
    workstation_id = instance.id
    workstation_ip = instance.public_ip_address
    print(workstation_id)
    print(workstation_ip)

#############################################################################################################################

#Attach Forensic(compromised) Volume to the SIFT Workstation Instance

print('\n===> ATTACHING FORENSIC(compromised) VOLUME TO SIFT WORKSTATION.. \n')

for_vol_attach = vpc_client.attach_volume(
    Device = data.ForVolDevice_value,
    InstanceId = workstation_id,
    VolumeId = selected_volume_id
    )
print('===> FORENSIC VOLUME SUCCESSFULLY ATTACHED\n')

#############################################################################################################################

#Attach Snapshot Volume to SIFT Workstation Instance

print('===> ATTACHING SNAPSHOT VOLUME TO SIFT WORKSTATION.. \n')

snapshot_vol_attach = vpc_client.attach_volume(
    Device = data.SnapshotVolDevice_value,
    InstanceId = workstation_id,
    VolumeId = snapshot_vol_id
    )
print('===> SNAPSHOT VOLUME SUCCESSFULLY ATTACHED\n')

#############################################################################################################################

##SSH into SIFT Workstation and mount Volumes

# Mount Forensic(compromised) Volume 
# -> mkdir /mnt/compromised_data
# -> mount /dev/xvdf1 /mnt/compromised_data
#---------
# Mount Snapshot Volume 
# -> mkdir /mnt/snapshot_data
# -> mount /dev/xvdg /mnt/snapshot_data

print('===> MOUNTING VOLUME TO SIFT WORKSTATION..\n')
instance_conn = paramiko.SSHClient()
instance_conn.load_system_host_keys()
instance_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
instance_conn.connect(workstation_ip, port=data.ConnPort_value, username=data.ConnUsername_value, key_filename=data.ConnKeyFilename_value)
command = data.MountVolumes_value
(stdin, stdout, stderr) = instance_conn.exec_command(command)
for std_out in stdout.readlines()
    print std_out
    instance_conn.close()

print('\n===> FORENSIC VOLUME MOUNTED TO SIFT WORKSTATION')
print('\n===> READY FOR ANALYSIS::')
