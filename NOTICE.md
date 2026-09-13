# Third-party notices

KatipAI itself is licensed under the [MIT License](LICENSE).
The application downloads and uses third-party models and libraries.
By using those models you accept their respective licenses.

## Runtime libraries (selected)

These are installed via `pip` / `npm`. Each package ships its own license
(typically MIT, Apache-2.0, or BSD). See the metadata of the installed package
for the authoritative text.

| Component | Typical license | Notes |
|-----------|-----------------|-------|
| FastAPI, Uvicorn, Pydantic, SQLAlchemy | MIT | HTTP API and persistence |
| NumPy, SciPy | BSD | Audio math |
| Silero VAD | MIT | Voice activity detection |
| ONNX Runtime | MIT | Speaker embedding inference |
| sounddevice | MIT | Microphone capture |
| mlx-whisper, mlx-lm | MIT (package) | Apple Silicon inference wrappers; **macOS only** |
| React, Vite, Tailwind CSS, lucide-react | MIT | Web UI |

## Speech and language models

Models are downloaded from Hugging Face on first use (~4.5 GB total).
KatipAI does not redistribute model weights.

| Role | Default repository | License notes |
|------|--------------------|---------------|
| STT | `mlx-community/whisper-large-v3-turbo` | Derived from OpenAI Whisper (MIT). Confirm the model card. |
| STT fallback | `mlx-community/whisper-medium-mlx` | Same family; confirm the model card. |
| LLM | `mlx-community/Qwen3.5-4B-OptiQ-4bit` | Qwen models are typically released under the [Qwen license](https://huggingface.co/Qwen) (not MIT). Confirm the model card before commercial use. |
| LLM fallback | `mlx-community/Qwen2.5-3B-Instruct-4bit` | Same family; confirm the model card. |
| Speaker embedding | sherpa-onnx-style ONNX (see `scripts/download_voice_model.py`) | Check the upstream sherpa-onnx / model license before redistribution. |

## Native helper

The ScreenCaptureKit helper under `tools/system_audio/` is part of KatipAI
(MIT). Build it from source with `tools/system_audio/build_helper.sh`.
Prebuilt `.app` bundles and `.build/` artifacts are not committed.

## Hugging Face downloads

The first transcription or summarization run pulls weights from Hugging Face.
If your environment requires authentication, set a standard `HF_TOKEN`.
KatipAI does not read or store that token itself.
