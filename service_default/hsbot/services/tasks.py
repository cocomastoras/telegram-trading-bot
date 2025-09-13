import json
import os
import datetime
from google.cloud import tasks_v2
import grpc
from google.cloud.tasks_v2.services.cloud_tasks.transports import CloudTasksGrpcAsyncIOTransport

PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')
LOCATION = "europe-west1"


class CloudTaskAsyncClientFactory:
    """
        Singleton class to produce a single firestore client
        and serve it instead of creating multiple
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            if not os.getenv('GAE_ENV', '').startswith('standard'):
                channel = grpc.aio.insecure_channel('localhost:8123')
                transport = CloudTasksGrpcAsyncIOTransport(channel=channel)
                cls._instance = tasks_v2.CloudTasksAsyncClient(transport=transport)
            else:
                cls._instance = tasks_v2.CloudTasksAsyncClient()
        return cls._instance


async def create_delete_message_task(user_id: str, chat_id: str, message_id: str, delay: int = 0):
    task_client = CloudTaskAsyncClientFactory()
    queue_name = "delete-tg-messages"
    queue_path = task_client.queue_path(PROJECT_ID, LOCATION, queue_name)

    _task = {
        'app_engine_http_request': {
            'http_method': tasks_v2.HttpMethod.POST,
            'relative_uri': '/worker/delete-tg-message',
            'body': json.dumps(
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "message_id": message_id
                }
            ).encode(),
            'headers': {
                "Content-type": "application/json"
            }
        }
    }

    if delay > 0:
        eta = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=delay)
        _task.update(
            {
                'schedule_time': eta
            }
        )

    await task_client.create_task(parent=queue_path, task=_task)
