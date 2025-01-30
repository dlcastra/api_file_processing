from app.constants import MAX_FILE_SIZE_BYTES, SUPPORTED_FORMATS


class FileValidator:
    def __init__(self):
        self.file = None

    def validate_file(self, file) -> bool:
        self.file = file

        return all(
            [self.file_type_is_supported(), self.file_size_is_valid(), not self.file_name_is_more_than_128_characters()]
        )

    def file_type_is_supported(self):
        """Returns True if the file type is supported and False otherwise."""
        file_format = self.file.filename.split(".")[-1]
        return file_format in SUPPORTED_FORMATS

    def file_size_is_valid(self):
        """Returns True if the size of the file is less or equal MAX_FILE_SIZE_BYTES and False otherwise."""
        file_size = self.file.size
        return file_size <= MAX_FILE_SIZE_BYTES

    def file_name_is_more_than_128_characters(self):
        """Returns True if the file name length is more than 128 characters long and False otherwise."""
        file_name = self.file.filename
        return len(file_name) > 128


invalid_file = {
    "file_name": "max length is 128 characters",
    "max_size": "20 MB",
    "supported_formats": SUPPORTED_FORMATS,
}
