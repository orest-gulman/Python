import boto3
import time
from datetime import date

region_source = 'us-east-1'
region_dest = 'us-east-2'

client_source = boto3.client('ec2', region_name=region_source)
client_dest = boto3.client('ec2', region_name=region_dest)
ec2_resource = boto3.resource('ec2')


# Getting snapshots as per specified filter and only today created
def get_snapshots():
    response = client_source.describe_snapshots(
        Filters=[{'Name': 'tag:Disaster_Recovery', 'Values': ['Full']}]
    )
    snapshotsInDay = []
    for i in response["Snapshots"]:
        if i["StartTime"].strftime('%Y-%m-%d') == date.isoformat(date.today()):
            snapshotsInDay.append(i)
    return snapshotsInDay


# Creating a list of snapshot_id and respective tags
def get_snapshot_list(snapshots):
    snapshot_list = []
    for snapshot in snapshots:
        snapshot_id = snapshot["SnapshotId"]
        snapshot_tags = snapshot["Tags"]
        snapshot_list.append((snapshot_id, snapshot_tags))
    return snapshot_list


# Copying snapshot with tags
def copy_snapshot(snapshot_id, snapshot_tags):
    try:
        copy_response = client_dest.copy_snapshot(
            Description='[Disaster Recovery] copied from us-east-1',
            SourceRegion=region_source,
            SourceSnapshotId=snapshot_id,
            DryRun=False,
            #           Encrypted=True,
            #           KmsKeyId='1e287363-89f6-4837-a619-b550ff28c211',
        )
    except Exception as e:
        raise e

    new_snapshot_id = copy_response["SnapshotId"]
    print(
        "Started copying.. snapshot_id: " + snapshot_id + " from: " + region_source + " to: " + region_dest + " with new snapshot_id: " + new_snapshot_id)

    # Creating tags in snapshot in destination region
    tag_source = [new_snapshot_id]
    tag = client_dest.create_tags(
        DryRun=False,
        Resources=tag_source,
        Tags=snapshot_tags
    )
    return new_snapshot_id


def lambda_handler(event, context):
    snapshots = get_snapshots()
    snapshot_list = get_snapshot_list(snapshots)
    # print(*snapshot_list, sep="\n")
    for i in snapshot_list:
        snapshot_id = i[0]
        snapshot_tags = i[1]
    #   snapshot_tags_filtered = ([item for item in snapshot_tags if item['Key'] != 'aws:backup:source-resource'])
        new_snapshot_id = copy_snapshot(snapshot_id, snapshot_tags)
