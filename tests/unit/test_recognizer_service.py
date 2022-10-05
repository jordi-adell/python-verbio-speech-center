import unittest
import random
import string
import tempfile
import numpy as np

from asr4.recognizer import RecognizerService
from asr4.recognizer import RecognizeRequest
from asr4.recognizer import RecognitionConfig
from asr4.recognizer import RecognitionParameters
from asr4.recognizer import RecognitionResource
from asr4.recognizer import RecognizeResponse
from asr4.recognizer import Session, OnnxRuntime
from asr4.types.language import Language

from typing import Any, Dict, List, Optional, Union

DEFAULT_ENGLISH_MESSAGE: str = "hello i am up and running received a message from you"
DEFAULT_SPANISH_MESSAGE: str = (
    "hola estoy  levantado y en marcha  y he recibido un mensaje tuyo"
)
DEFAULT_CORRECT_SPANISH_MESSAGE: str = (
    "hola estoy levantado y en marcha y he recibido un mensaje tuyo"
)
FORMATTED_SPANISH_MESSAGE: str = (
    "Hola. Estoy levantado y en marcha y he recibido un mensaje tuyo."
)
DEFAULT_PORTUGUESE_MESSAGE: str = "ola  estou de pe recebi uma mensagem sua"
DEFAULT_CORRECT_PORTUGUESE_MESSAGE: str = "ola estou de pe recebi uma mensagem sua"


class MockOnnxSession(Session):
    def __init__(
        self,
        _path_or_bytes: Union[str, bytes],
        **kwargs,
    ) -> None:
        self._message = {
            Language.EN_US: DEFAULT_ENGLISH_MESSAGE,
            Language.ES: DEFAULT_SPANISH_MESSAGE,
            Language.PT_BR: DEFAULT_PORTUGUESE_MESSAGE,
        }.get(kwargs.get("language"), DEFAULT_ENGLISH_MESSAGE)

    def run(
        self,
        _output_names: Optional[List[str]],
        input_feed: Dict[str, Any],
        **kwargs,
    ) -> np.ndarray:
        defaultMessage = list(self._message.replace(" ", "|"))
        return [self._generateDefaultMessageArray(defaultMessage)]

    def _generateDefaultMessageArray(self, defaultMessage: List[str]) -> np.ndarray:
        defaultMessageArray = np.full(
            (1, len(defaultMessage), len(OnnxRuntime.DEFAULT_VOCABULARY)),
            -10.0,
            np.float32,
        )
        for (i, letter) in enumerate(defaultMessage):
            defaultMessageArray[
                0, i, OnnxRuntime.DEFAULT_VOCABULARY.index(letter)
            ] = 10.0
        return self._insertBlankBetweenRepeatedLetters(
            defaultMessage, defaultMessageArray
        )

    def _insertBlankBetweenRepeatedLetters(
        self, defaultMessage: List[str], defaultMessageArray: np.ndarray
    ) -> np.ndarray:
        lastLetter, offset = "", 0
        blank_row = self._getBlankArray()
        for (i, letter) in enumerate(defaultMessage):
            if lastLetter == letter:
                defaultMessageArray = np.insert(
                    defaultMessageArray, i + offset, blank_row, axis=1
                )
                offset += 1
            lastLetter = letter
        return defaultMessageArray

    def _getBlankArray(self) -> np.ndarray:
        blank_row = np.zeros(len(OnnxRuntime.DEFAULT_VOCABULARY), dtype=np.float32)
        blank_row[OnnxRuntime.DEFAULT_VOCABULARY.index("<s>")] = 10.0
        return blank_row

    def get_inputs_names(self) -> List[str]:
        return ["input"]


class TestRecognizerService(unittest.TestCase):
    def testVocabulary(self):
        labels = ["|", "<s>", "</s>", "<pad>"]
        with self.assertRaises(FileNotFoundError):
            RecognizerService(MockOnnxSession(""), vocabularyPath="")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            vocabularyPath = f.name
            for l in labels:
                f.write(f"{l}\n")
        service = RecognizerService(MockOnnxSession(""), vocabularyPath=vocabularyPath)
        self.assertEqual(service._runtime._decoder.labels, labels)

    def testInvalidAudio(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="en-US", sample_rate_hz=16000
                ),
                resource=RecognitionResource(topic="GENERIC"),
            ),
            audio=b"",
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidTopic(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="en-US", sample_rate_hz=16000
                ),
                resource=RecognitionResource(topic=-1),
            ),
            audio=b"SOMETHING",
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidLanguage(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="", sample_rate_hz=16000),
                resource=RecognitionResource(topic="GENERIC"),
            ),
            audio=b"SOMETHING",
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="INVALID", sample_rate_hz=16000
                ),
                resource=RecognitionResource(topic="GENERIC"),
            ),
            audio=b"SOMETHING",
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidSampleRate(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="en-US", sample_rate_hz=16001
                ),
                resource=RecognitionResource(topic="GENERIC"),
            ),
            audio=b"SOMETHING",
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="en-US", sample_rate_hz=8000),
                resource=RecognitionResource(topic="GENERIC"),
            ),
            audio=b"SOMETHING",
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestEmpty(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest()
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestAudio(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(audio=b"SOMETHING")
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestResource(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(resource=RecognitionResource(topic="GENERIC"))
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestLanguage(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="en-US"),
            )
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestSampleRate(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(sample_rate_hz=16000),
            )
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestParameters(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="en-US", sample_rate_hz=16000
                ),
            )
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testInvalidRecognizeRequestConfig(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="en-US", sample_rate_hz=16000
                ),
                resource=RecognitionResource(topic="GENERIC"),
            )
        )
        with self.assertRaises(ValueError):
            service.eventSource(request)

    def testRecognizeRequest(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(
                    language="en-US", sample_rate_hz=16000
                ),
                resource=RecognitionResource(topic="GENERIC"),
            ),
            audio=b"SOMETHING",
        )
        self.assertFalse(service.eventSource(request))

    def testInvalidRecognizeRequestHandle(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(),
            )
        )
        with self.assertRaises(ValueError):
            service.eventHandle(request)

    def testRecognizeRequestHandleEnUs(self):
        service = RecognizerService(MockOnnxSession(""))
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="en-US"),
            ),
            audio=b"0000",
        )
        self.assertEqual(
            service.eventHandle(request),
            DEFAULT_ENGLISH_MESSAGE,
        )

    def testRecognizeRequestHandleEs(self):
        service = RecognizerService(
            MockOnnxSession("", language=Language.ES), Language.ES
        )
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="es"),
            ),
            audio=b"0000",
        )
        self.assertEqual(
            service.eventHandle(request),
            DEFAULT_CORRECT_SPANISH_MESSAGE,
        )

    def testRecognizeRequestHandlePtBr(self):
        service = RecognizerService(
            MockOnnxSession("", language=Language.PT_BR),
            Language.PT_BR,
        )
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="pt-BR"),
            ),
            audio=b"0000",
        )
        self.assertEqual(
            service.eventHandle(request), DEFAULT_CORRECT_PORTUGUESE_MESSAGE
        )

    def testRecognizeRequestSink(self):
        service = RecognizerService(MockOnnxSession(""))
        response = "".join(random.choices(string.ascii_letters + string.digits, k=16))
        self.assertEqual(service.eventSink(response), RecognizeResponse(text=response))

    def testRecognizeFormatter(self):
        service = RecognizerService(
            MockOnnxSession("", language=Language.ES),
            Language.ES,
            formatterPath="/mnt/shared/squad2/projects/asr4models/formatter/format-model.es-es-1.1.0.fm",
        )
        request = RecognizeRequest(
            config=RecognitionConfig(
                parameters=RecognitionParameters(language="es"),
            ),
            audio=b"0000",
        )
        self.assertEqual(
            service.eventHandle(request),
            FORMATTED_SPANISH_MESSAGE,
        )
