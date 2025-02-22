from enum import Enum


class ResponseErrorMessage(str, Enum):
    # Object error responses
    FILE_DOES_NOT_EXIST = "File does not exist"
    FILE_PROCESSING_ERROR = "An error occurred while processing file"

    # AWS error responses
    QUEUE_ERROR = "Error while sending message to the queue"
    SQS_ENQUEUE_TASK_ERROR = "Failed to enqueue task in SQS"

    # Webhook error
    TIMEOUT_ERROR = "Timeout while waiting for analysis result"

    # Server error responses
    INTERNAL_ERROR = "Internal server error"


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
