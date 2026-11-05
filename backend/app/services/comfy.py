from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from ..config import COMFY_URL

DEFAULT_PROFILE: dict[str, Any] = {
    "unet_name": "PornMaster_Moss_SFT_V1_int8_convrot.safetensors",
    "clip_name": "qwen3.5_9b_int8_convrot.safetensors",
    "clip_type": "moss_image",
    "vae_name": "flux2-vae_small.safetensors",
    "width": 848,
    "height": 1488,
    "batch_size": 1,
    "steps": 25,
    "cfg": 2.5,
    "sampler_name": "er_sde",
    "scheduler": "simple",
    "denoise": 1.0,
    "filename_prefix": "mioss",
    "spectrum": {
        "warmup_steps": 7,
        "detail_guard_steps": 1,
        "tail_actual_steps": 1,
        "post_guard_horizon_cap": 2,
        "window_size": 2.0,
        "flex_window": 0.5,
        "cache_device": "main_device",
        "error_tolerance": 1.0,
        "debug": False,
        "warn_unverified_sampler": False,
    },
}


def build_graph(prompt: str, negative: str, seed: int, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**DEFAULT_PROFILE, **(profile or {})}
    spectrum = {**DEFAULT_PROFILE["spectrum"], **(merged.get("spectrum") or {})}
    return {
        "28": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": merged["unet_name"], "weight_dtype": "default"},
        },
        "29": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": merged["clip_name"], "type": merged["clip_type"], "device": "default"},
        },
        "27": {"class_type": "VAELoader", "inputs": {"vae_name": merged["vae_name"]}},
        "30": {"class_type": "SpectrumMOSSImageAdaptive", "inputs": {"model": ["28", 0], **spectrum}},
        "25": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["29", 0]}},
        "26": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["29", 0]}},
        "22": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": int(merged["width"]),
                "height": int(merged["height"]),
                "batch_size": int(merged["batch_size"]),
            },
        },
        "16": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["30", 0],
                "seed": int(seed),
                "steps": int(merged["steps"]),
                "cfg": float(merged["cfg"]),
                "sampler_name": merged["sampler_name"],
                "scheduler": merged["scheduler"],
                "positive": ["25", 0],
                "negative": ["26", 0],
                "latent_image": ["22", 0],
                "denoise": float(merged["denoise"]),
            },
        },
        "23": {"class_type": "VAEDecode", "inputs": {"samples": ["16", 0], "vae": ["27", 0]}},
        "13": {
            "class_type": "SaveImage",
            "inputs": {"images": ["23", 0], "filename_prefix": merged["filename_prefix"]},
        },
    }


class ComfyClient:
    def __init__(self, base_url: str = COMFY_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))

    def close(self) -> None:
        self.client.close()

    def health(self) -> dict[str, Any]:
        try:
            response = self.client.get(f"{self.base_url}/system_stats")
            if response.status_code != 200:
                return {"ok": False, "error": f"HTTP {response.status_code}"}
            return {"ok": True, "data": response.json()}
        except Exception as error:
            return {"ok": False, "error": str(error)}

    def queue(self, graph: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(
            f"{self.base_url}/prompt",
            json={"prompt": graph, "client_id": uuid.uuid4().hex},
        )
        if response.status_code != 200:
            raise RuntimeError(f"ComfyUI queue failed: {response.status_code} {response.text[:1000]}")
        return response.json()

    def history(self, prompt_id: str) -> dict[str, Any]:
        response = self.client.get(f"{self.base_url}/history/{prompt_id}")
        response.raise_for_status()
        return response.json()

    def wait(self, prompt_id: str, timeout: float = 900.0) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            history = self.history(prompt_id)
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(1)
        raise TimeoutError(f"ComfyUI prompt did not finish: {prompt_id}")

    def queue_status(self) -> dict[str, Any]:
        response = self.client.get(f"{self.base_url}/queue")
        response.raise_for_status()
        return response.json()

    def delete_pending(self, prompt_ids: list[str]) -> None:
        response = self.client.post(f"{self.base_url}/queue", json={"delete": prompt_ids})
        response.raise_for_status()

    def interrupt(self) -> None:
        response = self.client.post(f"{self.base_url}/interrupt")
        response.raise_for_status()

    @staticmethod
    def output_image(history_entry: dict[str, Any]) -> dict[str, Any] | None:
        for output in (history_entry.get("outputs") or {}).values():
            for image in output.get("images") or []:
                return image
        return None

    def download(self, image: dict[str, Any]) -> bytes:
        response = self.client.get(
            f"{self.base_url}/view",
            params={
                "filename": image["filename"],
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            },
        )
        response.raise_for_status()
        return response.content
