import os, sys

PROTO_PATH="proto"
PROTO_FILE_EXTENSION = ".proto"
PROTO_PATH_GENERATED = os.path.join(os.getcwd(),"proto","generated")

for file in os.listdir(PROTO_PATH):
    if file.endswith(PROTO_FILE_EXTENSION):
        print(f"Start compiling: {file}")
        PROTO_DIR = os.path.abspath(PROTO_PATH)
        print(f"Generating new proto file: PROTO_DIR={PROTO_DIR} PROTO_FILE={file}")
        os.makedirs(PROTO_PATH_GENERATED, exist_ok=True)
        # Next line could be improved
        retv = os.system(f"python -m grpc_tools.protoc --proto_path={PROTO_DIR} --python_out={PROTO_PATH_GENERATED} --grpc_python_out={PROTO_PATH_GENERATED} {file}")
        if retv == 0:
            print(f"DONE: {file} compiled")
        else:
            print(f"ERROR: Some error happened during compilation of {file}")
            sys.exit(-1)
