#!/usr/bin/env python3
"""
Hugging Face Görsel Üretim Scripti
Codex ile kullanıma uygun.

Kurulum:
    pip install huggingface_hub diffusers torch accelerate pillow

Kullanım (API - Bulut):
    export HF_TOKEN="huggingface_tokenınız"
    python generate_image.py "A futuristic city at sunset, cyberpunk style"

Kullanım (Yerel - GPU Gerekir):
    python generate_image.py "A futuristic city at sunset" --local

Token almak için: https://huggingface.co/settings/tokens
"""

import os
import sys
import argparse


def generate_via_api(prompt: str, model: str = "black-forest-labs/FLUX.1-schnell", output_path: str = "output.png"):
    """Hugging Face Inference API (Bulut) ile görsel üret."""
    try:
        from huggingface_hub import InferenceClient
    except ImportError:
        print("huggingface_hub kütüphanesi eksik. Kurulum:")
        print("  pip install huggingface_hub")
        sys.exit(1)

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HATA: HF_TOKEN çevre değişkeni ayarlanmamış.")
        print("1. Token al: https://huggingface.co/settings/tokens")
        print("2. Export et: export HF_TOKEN='your_token'")
        sys.exit(1)

    client = InferenceClient(api_key=token)
    print(f"Prompt: {prompt}")
    print(f"Model: {model}")
    print("Görsel üretiliyor (Bulut API)...")

    # InferenceClient text_to_image PIL.Image objesi döndürür
    image = client.text_to_image(prompt=prompt, model=model)
    image.save(output_path)
    print(f"✅ Görsel kaydedildi: {output_path}")


def generate_via_local(prompt: str, model: str = "stabilityai/stable-diffusion-2-1", output_path: str = "output.png"):
    """Yerel diffusers ile görsel üret (GPU/VRAM gerektirir)."""
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
    except ImportError:
        print("diffusers ve torch eksik. Kurulum:")
        print("  pip install diffusers torch accelerate safetensors")
        sys.exit(1)

    print(f"Prompt: {prompt}")
    print(f"Model: {model}")
    print("Model indiriliyor / yükleniyor (ilk seferde uzun sürebilir)...")

    pipe = AutoPipelineForText2Image.from_pretrained(
        model,
        torch_dtype=torch.float16,
        use_safetensors=True,
    )

    # VRAM optimizasyonu: model CPU/GPU arasında otomatik taşınır
    pipe.enable_model_cpu_offload()

    image = pipe(prompt).images[0]
    image.save(output_path)
    print(f"✅ Görsel kaydedildi: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HF Görsel Üretme")
    parser.add_argument("prompt", help="Görsel açıklaması (prompt)")
    parser.add_argument("--api", action="store_true", default=True, help="Bulut API kullan (varsayılan)")
    parser.add_argument("--local", action="store_true", help="Yerel model kullan (GPU gerekir)")
    parser.add_argument("--model", default=None, help="Hugging Face model ID (örn: stabilityai/stable-diffusion-xl-base-1.0)")
    parser.add_argument("--output", default="output.png", help="Çıktı dosya adı")
    args = parser.parse_args()

    if args.local:
        model = args.model or "stabilityai/stable-diffusion-2-1"
        generate_via_local(args.prompt, model=model, output_path=args.output)
    else:
        model = args.model or "black-forest-labs/FLUX.1-schnell"
        generate_via_api(args.prompt, model=model, output_path=args.output)
