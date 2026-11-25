#!/usr/bin/env python3
"""Exercise signed S3 CRUD against an opt-in disposable SeaweedFS mini instance.

No production data, no secret printing, no bucket wipe, no service exposure.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError


BUCKET = "goreecloud-preview"


def main() -> int:
    if sys.argv[1:] != ["--disposable"]:
        print("Usage: python3 scripts/s3_preview_smoke.py --disposable", file=sys.stderr)
        print("The test writes and deletes one disposable S3 object. Never target real data.", file=sys.stderr)
        return 2
    port = int(os.environ.get("GC_S3_PORT", "8333"))
    if not 1 <= port <= 65535:
        raise ValueError("Invalid S3 localhost test port")
    endpoint = f"http://127.0.0.1:{port}"
    key_id = os.environ["GC_S3_ACCESS_KEY"]
    secret = os.environ["GC_S3_SECRET_KEY"]
    if len(key_id) < 20 or len(secret) < 32:
        raise ValueError("S3 preview credentials are not generated or secure enough")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint, region_name="us-east-1",
        aws_access_key_id=key_id, aws_secret_access_key=secret,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      connect_timeout=4, read_timeout=5, retries={"max_attempts": 1}),
    )
    until = time.monotonic() + 90
    while True:
        try:
            buckets = s3.list_buckets()["Buckets"]
            break
        except (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError):
            if time.monotonic() >= until:
                raise RuntimeError("S3 preview was not ready within the test window") from None
            time.sleep(2)
        except ClientError:
            raise RuntimeError("S3 preview rejected the generated signed credentials") from None
    if not any(bucket["Name"] == BUCKET for bucket in buckets):
        s3.create_bucket(Bucket=BUCKET)

    # A read-only unsigned client must not be able to list the private bucket.
    try:
        with urlopen(endpoint + "/" + BUCKET + "?list-type=2", timeout=6) as anonymous:
            raise AssertionError(f"Unsigned S3 bucket listing was exposed (HTTP {anonymous.status})")
    except HTTPError as error:
        assert error.code in (401, 403), "Expected unsigned listing rejection"
    except URLError as error:
        raise RuntimeError("S3 gateway disappeared during authorization check") from error

    object_key = "ci/" + uuid4().hex + ".txt"
    data = b"GoreeCloud Database isolated S3 preview CI fixture"
    try:
        s3.put_object(Bucket=BUCKET, Key=object_key, Body=data, ContentType="text/plain")
        response = s3.get_object(Bucket=BUCKET, Key=object_key)
        downloaded = response["Body"].read()
        assert hashlib.sha256(downloaded).digest() == hashlib.sha256(data).digest()
        listed = s3.list_objects_v2(Bucket=BUCKET, Prefix=object_key)
        assert any(obj["Key"] == object_key for obj in listed.get("Contents", []))
    finally:
        s3.delete_object(Bucket=BUCKET, Key=object_key)
    try:
        s3.head_object(Bucket=BUCKET, Key=object_key)
        raise AssertionError("S3 deletion was not observed")
    except ClientError as error:
        assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 404

    print("Isolated signed S3 protocol smoke passed: unauthorized list denied; put/get/list/delete verified.")
    print("This is a separate preview, not the existing PostgreSQL object API or production storage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
