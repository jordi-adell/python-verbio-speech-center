import argparse, os, sys, toml
from loguru import logger
import multiprocessing

from asr4_streaming.recognizer import Server, ServerConfiguration
from asr4_streaming.recognizer import Logger

from asr4_engine.data_classes import Language
from asr4.engines.wav2vec.v1.runtime.onnx import DecodingType


def main():
    multiprocessing.set_start_method("spawn", force=True)
    args = Asr4ArgParser(sys.argv[1:]).getArgs()
    _ = Logger(args.verbose)
    serve(ServerConfiguration(args))


def serve(
    configuration,
) -> None:
    servers = []
    for i in range(configuration.numberOfServers):
        logger.info("Starting server %s" % i)
        server = Server(configuration)
        server.spawn()
        servers.append(server)

    for server in servers:
        server.join()


class Asr4ArgParser:
    def __init__(self, argv):
        self.argv = argv

    def getArgs(self) -> argparse.Namespace:
        args = Asr4ArgParser.parseArguments(self.argv)
        args = Asr4ArgParser.replaceUndefinedWithEnvVariables(args)
        args = Asr4ArgParser.replaceUndefinedWithConfigFile(args)
        args = Asr4ArgParser.replaceUndefinedWithDefaultValues(args)
        args = Asr4ArgParser.fixNumberOfJobs(args)
        args = Asr4ArgParser.checkArgsRequired(args)
        return args

    def parseArguments(args: list) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Python ASR4 Server")
        parser.add_argument(
            "-v",
            "--verbose",
            type=str,
            choices=Logger.getLevels(),
            help="Log levels. By default reads env variable LOG_LEVEL.",
        )
        parser.add_argument(
            "--host",
            dest="bindAddress",
            help="Hostname address to bind the server to.",
        )
        parser.add_argument(
            "-C", "--config", dest="config", help="Path to the asr4 config file"
        )
        return parser.parse_args(args)

    def replaceUndefinedWithEnvVariables(
        args: argparse.Namespace,
    ) -> argparse.Namespace:
        args.verbose = args.verbose or os.environ.get(
            "LOG_LEVEL", Logger.getDefaultLevel()
        )
        return args

    def replaceUndefinedWithConfigFile(args: argparse.Namespace) -> argparse.Namespace:
        configFile = args.config or "asr4_config.toml"
        if os.path.exists(configFile):
            config = toml.load(configFile)
            config.setdefault("global", {})
            args = Asr4ArgParser.fillArgsFromTomlFile(args, config)
        return args

    def fillArgsFromTomlFile(args: argparse.Namespace, config):
        if config["global"].setdefault("host") and config["global"].setdefault("port"):
            args.bindAddress = f"{config['global']['host']}:{config['global']['port']}"
            del config["global"]["host"]
            del config["global"]["port"]
        for k, v in config["global"].items():
            setattr(args, k, getattr(args, k, None) or v)
        return args

    def replaceUndefinedWithDefaultValues(
        args: argparse.Namespace,
    ) -> argparse.Namespace:
        args.bindAddress = args.bindAddress or "[::]:50051"
        args.gpu = bool(args.gpu) if "gpu" in args else False
        args.servers = int(args.servers) if "servers" in args else 1
        args.listeners = int(args.listeners) if "listeners" in args else 1
        args.workers = int(args.workers) if "workers" in args else 2
        args.decoding_type = args.decoding_type if "decoding_type" in args else "GLOBAL"
        args.lm_algorithm = args.lm_algorithm if "lm_algorithm" in args else "viterbi"
        args.lm_weight = float(args.lm_weight) if "lm_weight" in args else 0.2
        args.word_score = float(args.word_score) if "word_score" in args else -1
        args.sil_score = float(args.sil_score) if "sil_score" in args else 0
        args.overlap = int(args.overlap) if "overlap" in args else 0
        args.subwords = bool(args.subwords) if "subwords" in args else False
        args.local_formatting = (
            bool(args.local_formatting) if "local_formatting" in args else False
        )
        args.maxChunksForDecoding = (
            int(args.maxChunksForDecoding) if "maxChunksForDecoding" in args else 1
        )
        return args

    def fixNumberOfJobs(args):
        if "jobs" in args:
            args.servers = 1
            args.workers = 0
            args.listeners = args.jobs
        return args

    def checkArgsRequired(args: argparse.Namespace) -> argparse.Namespace:
        if not args.model:
            (
                cpu_dict_path,
                cpu_model_path,
                gpu_dict_path,
                gpu_model_path,
                standard_dict_path,
                standard_model_path,
            ) = Asr4ArgParser.setStandardModelPaths(args)
            Asr4ArgParser.constructModelPaths(
                args,
                cpu_dict_path,
                cpu_model_path,
                gpu_dict_path,
                gpu_model_path,
                standard_dict_path,
                standard_model_path,
            )

            if not (args.model or args.vocabulary):
                raise ValueError(
                    "No model/dict was specified and it couldn't be found on the standard paths/naming"
                )

        if args.lm_algorithm == "kenlm" and not (args.lm_model or args.lexicon):
            (
                lm_lexicon_path,
                lm_model_path,
                lm_version_lexicon_path,
                lm_version_model_path,
            ) = Asr4ArgParser.setStandardLMPaths(args)
            Asr4ArgParser.constructLMPaths(
                args,
                lm_lexicon_path,
                lm_model_path,
                lm_version_lexicon_path,
                lm_version_model_path,
            )

        if args.local_formatting and (
            not args.formatter or args.lm_algorithm != "kenlm"
        ):
            raise ValueError(
                "Local formatting was specified but no formatter model was given or lm algorithm is not kenlm"
            )

        return args

    def setStandardLMPaths(args):
        lm_model_path = f"asr4-{args.language.lower()}-lm.bin"
        lm_lexicon_path = f"asr4-{args.language.lower()}-lm.lexicon.txt"
        lm_version_model_path = f"asr4-{args.language.lower()}-lm-{args.lm_version}.bin"
        lm_version_lexicon_path = (
            f"asr4-{args.language.lower()}-lm-{args.lm_version}.lexicon.txt"
        )
        return (
            lm_lexicon_path,
            lm_model_path,
            lm_version_lexicon_path,
            lm_version_model_path,
        )

    def constructLMPaths(
        args,
        lm_lexicon_path,
        lm_model_path,
        lm_version_lexicon_path,
        lm_version_model_path,
    ):
        if os.path.exists(lm_model_path) and os.path.exists(lm_lexicon_path):
            args.lm_model = lm_model_path
            args.lexicon = lm_lexicon_path
        elif os.path.exists(lm_version_model_path) and os.path.exists(
            lm_version_lexicon_path
        ):
            args.lm_model = lm_version_model_path
            args.lexicon = lm_version_lexicon_path
        if args.lm_algorithm == "kenlm" and not (args.lm_model or args.lexicon):
            raise ValueError(
                "KenLM Language was specified but no Lexicon/LM could be found on the standards path naming"
            )

    def setStandardModelPaths(args):
        standard_model_path = f"asr4-{args.language.lower()}.onnx"
        standard_dict_path = "dict.ltr.txt"
        gpu_model_path = f"asr4-{args.language.lower()}-{args.gpu_version}.onnx"
        gpu_dict_path = f"asr4-{args.language.lower()}-{args.gpu_version}.dict.ltr.txt"
        cpu_model_path = f"asr4-{args.language.lower()}-{args.cpu_version}.onnx"
        cpu_dict_path = f"asr4-{args.language.lower()}-{args.cpu_version}.dict.ltr.txt"
        return (
            cpu_dict_path,
            cpu_model_path,
            gpu_dict_path,
            gpu_model_path,
            standard_dict_path,
            standard_model_path,
        )

    def constructModelPaths(
        args,
        cpu_dict_path,
        cpu_model_path,
        gpu_dict_path,
        gpu_model_path,
        standard_dict_path,
        standard_model_path,
    ):
        if os.path.exists(standard_model_path) and os.path.exists(standard_dict_path):
            args.model = standard_model_path
            args.vocabulary = standard_dict_path
        elif (
            args.gpu
            and os.path.exists(gpu_model_path)
            and os.path.exists(gpu_dict_path)
        ):
            args.model = gpu_model_path
            args.vocabulary = gpu_dict_path
        elif os.path.exists(cpu_model_path) and os.path.exists(cpu_dict_path):
            args.model = cpu_model_path
            args.vocabulary = cpu_dict_path


if __name__ == "__main__":
    main()
