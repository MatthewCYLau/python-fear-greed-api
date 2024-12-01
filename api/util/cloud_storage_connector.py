from google.cloud import storage
import io


class CloudStorageConnector:
    def __init__(
        self,
        bucket_name,
    ) -> None:

        self.bucket_name = bucket_name
        self.storage_client = storage.Client()

    def upload_pyplot_figure(self, figure, blob_name: str) -> str:
        buf = io.BytesIO()
        figure.savefig(buf, format="png")

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(buf, content_type="image/png", rewind=True)
        return blob.public_url
