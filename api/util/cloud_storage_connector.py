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

    def upload_json_file(self, json_file_name: str, json_file_path: str) -> str:
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(f"data/{json_file_name}")
        with open(json_file_path, "rb") as f:
            blob.upload_from_file(f, content_type="application/json")
        return blob.public_url

    def upload_pkl(self, stock_symbol: str, pkl_file_name: str, pkl_file_path: str):
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(f"models/{stock_symbol}/{pkl_file_name}")
        with open(pkl_file_path, "rb") as f:
            blob.upload_from_file(f)

    def download_pkl(self, stock_symbol: str, pkl_file_name: str):
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(f"models/{stock_symbol}/{pkl_file_name}")
        return blob.download_as_bytes()

    def pkl_exists(self, stock_symbol: str, pkl_file_name: str):
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(f"models/{stock_symbol}/{pkl_file_name}")
        return blob.exists()
