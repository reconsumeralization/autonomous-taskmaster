
# region MCP Tool: Generate Image with Gemini/Imagen API
# INPUT: prompt (str): The text prompt describing the image to generate.
# INPUT: model (str, optional): The model to use ("gemini" or "imagen3"). Default is "imagen3".
# INPUT: api_key (str, optional): The Gemini API key. If not provided, will use the GEMINI_API_KEY environment variable.
# INPUT: num_images (int, optional): Number of images to generate (1-4, Imagen 3 only). Default is 1.
# INPUT: aspect_ratio (str, optional): Aspect ratio for Imagen 3 ("1:1", "3:4", "4:3", "9:16", "16:9"). Default is "1:1".
# INPUT: output_path (str, optional): Path to save the generated image(s). If not provided, will use "generated_image_{i}.png".
# OUTPUT: List of file paths to the generated images.
import os
import requests
import base64
from typing import List, Optional

# MCP tool registration (for MCP server discovery)
MCP_TOOL = {
    "name": "generate_image",
    "description": "Generate image(s) using Gemini 2.0 Flash Experimental or Imagen 3 via Gemini API.",
    "parameters": {
        "prompt": {"type": "string", "description": "The text prompt describing the image to generate."},
        "model": {"type": "string", "description": "The model to use ('gemini' or 'imagen3').", "default": "imagen3"},
        "api_key": {"type": "string", "description": "The Gemini API key. If not provided, will use the GEMINI_API_KEY environment variable.", "optional": True},
        "num_images": {"type": "integer", "description": "Number of images to generate (1-4, Imagen 3 only).", "default": 1, "optional": True},
        "aspect_ratio": {"type": "string", "description": "Aspect ratio for Imagen 3 ('1:1', '3:4', '4:3', '9:16', '16:9').", "default": "1:1", "optional": True},
        "output_path": {"type": "string", "description": "Path to save the generated image(s). If not provided, will use 'generated_image_{i}.png'.", "optional": True}
    },
    "returns": {
        "type": "array",
        "items": {"type": "string"},
        "description": "List of file paths to the generated images."
    }
}

def mcp_tool_generate_image(
    prompt: str,
    model: str = "imagen3",
    api_key: Optional[str] = None,
    num_images: int = 1,
    aspect_ratio: str = "1:1",
    output_path: Optional[str] = None
) -> List[str]:
    """
    MCP Tool: Generate image(s) using Gemini 2.0 Flash Experimental or Imagen 3 via Gemini API.

    Returns list of file paths to generated images.
    """
    if api_key is None:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key not provided. Set GEMINI_API_KEY environment variable or pass api_key argument.")

    headers = {"Content-Type": "application/json"}
    images = []

    if model.lower() == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent?key={api_key}"
        data = {
            "contents": [{
                "parts": [
                    {"text": prompt}
                ]
            }],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}
        }
        resp = requests.post(url, headers=headers, json=data)
        if not resp.ok:
            raise RuntimeError(f"Gemini API error: {resp.status_code} {resp.text}")
        resp_json = resp.json()
        # Find all base64 image data in the response
        parts = []
        for candidate in resp_json.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "inline_data" in part and part["inline_data"].get("mime_type", "").startswith("image/"):
                    parts.append(part["inline_data"]["data"])
        if not parts:
            raise RuntimeError("No image data found in Gemini response.")
        for i, img_b64 in enumerate(parts):
            fname = output_path or f"generated_image_{i+1}.png"
            with open(fname, "wb") as f:
                f.write(base64.b64decode(img_b64))
            images.append(fname)
    elif model.lower() in ("imagen3", "imagen", "imagen-3"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={api_key}"
        data = {
            "instances": [
                {"prompt": prompt}
            ],
            "parameters": {
                "sampleCount": num_images,
                "aspectRatio": aspect_ratio
            }
        }
        resp = requests.post(url, headers=headers, json=data)
        if not resp.ok:
            raise RuntimeError(f"Imagen 3 API error: {resp.status_code} {resp.text}")
        resp_json = resp.json()
        preds = resp_json.get("predictions", [])
        if not preds:
            raise RuntimeError("No predictions found in Imagen 3 response.")
        for i, pred in enumerate(preds):
            img_b64 = pred.get("bytesBase64")
            if not img_b64:
                continue
            fname = output_path or f"generated_image_{i+1}.png"
            with open(fname, "wb") as f:
                f.write(base64.b64decode(img_b64))
            images.append(fname)
    else:
        raise ValueError("Unknown model. Use 'gemini' or 'imagen3'.")

    return images

# MCP tool entrypoint for MCP server
def mcp_entry_generate_image(params: dict) -> List[str]:
    """
    MCP tool entrypoint for generate_image.
    Expects params dict with keys matching MCP_TOOL['parameters'].
    """
    return mcp_tool_generate_image(
        prompt=params["prompt"],
        model=params.get("model", "imagen3"),
        api_key=params.get("api_key"),
        num_images=params.get("num_images", 1),
        aspect_ratio=params.get("aspect_ratio", "1:1"),
        output_path=params.get("output_path")
    )

# endregion MCP Tool: Generate Image with Gemini/Imagen API
