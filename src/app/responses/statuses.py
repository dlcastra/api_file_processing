from enum import Enum


class ResponseErrorMessage(str, Enum):
    # Object error responses
    FILE_DOES_NOT_EXIST = "File does not exist"
    FILE_PROCESSING_ERROR = "An error occurred while processing file"

    # AWS error responses
    AWS_MISSED_DOWNLOAD_AGS = "Either s3_key or (file_id and user_id) must be provided"
    AWS_QUEUE_ERROR = "Error while sending message to the queue"
    AWS_SQS_ENQUEUE_TASK_ERROR = "Failed to enqueue task in SQS"
    AWS_MISSED_CREDENTIALS = "AWS credentials not found"
    AWS_INCOMPLETE_CREDENTIALS = "Incomplete AWS credentials"

    # Webhook error
    TIMEOUT_ERROR = "Timeout while waiting for analysis result"

    # Server error responses
    INTERNAL_ERROR = "Internal server error"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
