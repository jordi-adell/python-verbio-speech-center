#!/usr/bin/env python3
import sys
import logging
sys.path.insert(1, '../proto/generated')

import grpc
import recognition_pb2_grpc
from concurrent.futures import ThreadPoolExecutor

from helpers.csr_client import CSRClient
from helpers.audio_importer import AudioImporter
from helpers.grpc_connection import GrpcConnection
from helpers.common import retrieve_token, parse_csr_commandline, RecognizerOptions


def process_recognition(executor: ThreadPoolExecutor, channel: grpc.Channel, options: RecognizerOptions, access_token: str):
    audio_resource = AudioImporter(options.audio_file, options.convert_audio)
    stub = recognition_pb2_grpc.RecognizerStub(channel)
    client = CSRClient(executor, stub, options, audio_resource, access_token)
    client.send_audio()
    client.wait_for_response()
    logging.info("Recognition finished")


def run(options: RecognizerOptions):
    logging.info("Connecting to %s", command_line_options.host)
    access_token = retrieve_token(command_line_options)
    grpc_connection = GrpcConnection(options.secure_channel, options.client_id, options.client_secret, access_token)

    with grpc_connection.open(options.host) as grpc_channel:
        executor = ThreadPoolExecutor()
        future = executor.submit(process_recognition, executor, grpc_channel, options, access_token)
        future.result()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='[%(asctime)s][%(levelname)s]:%(message)s',
                        handlers=[
                            logging.FileHandler("recognizer_stream.log"),
                            logging.StreamHandler()
                        ])
    logging.info("Running speechcenter streaming...")
    command_line_options = parse_csr_commandline()
    command_line_options.check()
    run(command_line_options)

