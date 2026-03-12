class MdToSpeechError(Exception):
    """Base application error."""


class ValidationError(MdToSpeechError):
    """Raised for invalid user input or invalid file state."""


class ModelIntegrationError(MdToSpeechError):
    """Raised when the TTS model cannot be loaded or invoked."""


class OllamaError(MdToSpeechError):
    """Raised when Ollama rewriting fails."""
