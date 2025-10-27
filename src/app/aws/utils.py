from typing import Tuple, Optional, Dict

from src.app.aws.clients import sqs_client
from src.app.responses.statuses import ResponseErrorMessage


async def send_message_to_sqs(sqs_url , request_body: str) -> Tuple[Optional[Dict[str, str | bool]], bool]:
    response = sqs_client.send_message(QueueUrl=sqs_url, MessageBody=request_body)
    status_code = response["ResponseMetadata"]["HTTPStatusCode"]
    if status_code != 200:
        return {"success": False, "message": ResponseErrorMessage.AWS_QUEUE_ERROR}, False
    elif "MessageId" not in response:
        return {"success": False, "message": ResponseErrorMessage.AWS_SQS_ENQUEUE_TASK_ERROR}, False
    return None, True
