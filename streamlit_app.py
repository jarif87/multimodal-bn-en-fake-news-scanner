# app.py
import streamlit as st
import torch
import numpy as np
from transformers import CLIPProcessor
from PIL import Image
import onnxruntime as ort
import os

def inject_css():
    st.markdown("""
    <style>
        .stApp {
            background-color: #000000;
            color: #ffffff;
            font-family: 'Segoe UI', sans-serif;
        }
        h1 {
            color: #4ade80;
            text-align: center;
            font-weight: 700;
            text-shadow: 0 0 10px rgba(74, 222, 128, 0.3);
            font-size: 2.6em;
            margin-bottom: 0.2em;
        }
        .subtitle {
            text-align: center;
            color: #e0e0e0;
            font-size: 1.15em;
            margin-bottom: 2rem;
            opacity: 0.9;
        }
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            border: 2px solid #4ade80 !important;
            border-radius: 16px !important;
            padding: 12px !important;
            background-color: rgba(0, 0, 0, 0.3) !important;
            color: white !important;
        }
        .stTextInput > div > div > input::placeholder,
        .stTextArea > div > div > textarea::placeholder {
            color: #aaa !important;
        }
        .stTextArea label, .stFileUploader label {
            color: #4ade80 !important;
            font-weight: 500;
            font-size: 1.1em;
        }
        .stFileUploader > div > div {
            border: 2px dashed #4ade80 !important;
            border-radius: 16px;
            padding: 20px;
            background-color: rgba(0, 0, 0, 0.2) !important;
            color: #e0e0e0;
        }
        .stButton > button {
            background-color: #4ade80 !important;
            color: #000 !important;
            font-weight: bold;
            font-size: 18px;
            padding: 12px 32px;
            border-radius: 24px;
            border: none;
            box-shadow: 0 0 15px rgba(74, 222, 128, 0.5);
            transition: all 0.3s ease;
            margin: 20px auto;
            display: block;
        }
        .stButton > button:hover {
            background-color: #22c55e !important;
            transform: scale(1.05);
            box-shadow: 0 0 20px rgba(74, 222, 128, 0.7);
        }
        .result-card {
            padding: 24px;
            border-radius: 16px;
            margin: 15px auto;
            max-width: 600px;
            text-align: center;
            font-size: 18px;
            border: 1px solid;
            background: rgba(0, 0, 0, 0.3);
        }
        .text-real, .image-real {
            border-color: #4ade80;
            color: #4ade80;
        }
        .text-fake, .image-fake {
            border-color: #ef4444;
            color: #ef4444;
        }
        .icon {
            font-size: 40px;
            margin-bottom: 8px;
        }
        .uploaded-image {
            border-radius: 16px;
            overflow: hidden;
            margin: 25px auto;
            max-width: 100%;
            border: 1px solid #4ade80;
        }
        .footer {
            text-align: center;
            color: #4ade80;
            font-size: 15px;
            margin-top: 50px;
            opacity: 0.85;
        }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def load_model_and_processor():
    try:
        current_dir = os.path.dirname(__file__)
        processor_path = os.path.join(current_dir, "clip_processor")
        onnx_path = os.path.join(current_dir, "clip_model", "train_quantized.onnx")

        processor = CLIPProcessor.from_pretrained(processor_path)

        if not os.path.exists(onnx_path):
            st.error(f"❌ ONNX model not found at: {onnx_path}")
            st.info("Make sure 'clip_model/train_quantized.onnx' exists.")
            return None, None, None

        session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        return session, processor, "onnx"
    except Exception as e:
        st.error(f"Failed to load model or processor: {str(e)}")
        return None, None, None

def predict_text_only(text, image, session, processor, device):
    inputs = processor(
        text=[text],
        images=image,
        return_tensors="np",
        padding="max_length",
        truncation=True,
        max_length=77
    )

    # Replace with zero image values for text-only
    inputs['pixel_values'] = np.zeros((1, 3, 224, 224), dtype=np.float32)
    mean = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32).reshape(1, 3, 1, 1)
    std = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32).reshape(1, 3, 1, 1)
    inputs['pixel_values'] = (inputs['pixel_values'] - mean) / std

    onnx_inputs = {
        "input_ids": np.array(inputs["input_ids"], dtype=np.int64),
        "attention_mask": np.array(inputs["attention_mask"], dtype=np.int64),
        "pixel_values": np.array(inputs["pixel_values"], dtype=np.float32)
    }

    logits = session.run(["logits"], onnx_inputs)[0]
    probs = torch.softmax(torch.from_numpy(logits[0]), dim=0).numpy()
    pred = np.argmax(probs)
    conf = probs[pred]
    return "Real" if pred == 1 else "Fake", conf

def predict_image_only(text, image, session, processor, device):
    inputs = processor(
        text=[text],
        images=image,
        return_tensors="np",
        truncation=True,
        max_length=77,
        do_convert_rgb=True,
        do_normalize=True,
        image_mean=[0.48145466, 0.4578275, 0.40821073],
        image_std=[0.26862954, 0.26130258, 0.27577711],
        input_data_format="channels_last"
    )

    # Zero out text inputs for image-only
    inputs['input_ids'].fill(0)
    inputs['attention_mask'].fill(0)

    onnx_inputs = {
        "input_ids": np.array(inputs["input_ids"], dtype=np.int64),
        "attention_mask": np.array(inputs["attention_mask"], dtype=np.int64),
        "pixel_values": np.array(inputs["pixel_values"], dtype=np.float32)
    }

    logits = session.run(["logits"], onnx_inputs)[0]
    probs = torch.softmax(torch.from_numpy(logits[0]), dim=0).numpy()
    pred = np.argmax(probs)
    conf = probs[pred]
    return "Real" if pred == 1 else "Fake", conf

def main():
    inject_css()
    st.set_page_config(page_title="Multimodal BN-EN Fake News Scanner", layout="centered")
    st.markdown("<h1>Multimodal BN-EN Fake News Scanner</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Enter text and upload an image to analyze <strong>text-only</strong> and <strong>image-only</strong> predictions.</p>", unsafe_allow_html=True)

    session, processor, device = load_model_and_processor()
    if session is None:
        st.stop()

    text_input = st.text_area("Enter News Text", placeholder="Type a headline or article snippet...", height=180)
    uploaded_image = st.file_uploader("Upload News Image", type=["jpg", "jpeg", "png"], help="Upload a related image")

    if st.button("Analyze Multimodal Input"):
        if not text_input.strip():
            st.warning("Please enter news text.")
        elif not uploaded_image:
            st.warning("Please upload a news image.")
        else:
            try:
                image = Image.open(uploaded_image).convert("RGB")
            except Exception as e:
                st.error(f"Cannot open image: {e}")
                return

            with st.spinner("Running text-only and image-only analysis..."):
                text_pred, text_conf = predict_text_only(text_input, image, session, processor, device)
                img_pred, img_conf = predict_image_only(text_input, image, session, processor, device)
                st.session_state.modality_results = {
                    "text": {"label": text_pred, "conf": text_conf},
                    "image": {"label": img_pred, "conf": img_conf}
                }

    if 'modality_results' in st.session_state:
        res = st.session_state.modality_results

        text_icon = "🟢" if res['text']['label'] == "Real" else "🔴"
        text_class = "text-real" if res['text']['label'] == "Real" else "text-fake"
        st.markdown(f"""
        <div class="result-card {text_class}">
            <div class="icon">{text_icon}</div>
            <div><strong>Text Analysis</strong></div>
            <div>Prediction: <strong>{res['text']['label']}</strong></div>
            <div>Confidence: {res['text']['conf']:.2%}</div>
        </div>
        """, unsafe_allow_html=True)

        img_icon = "🟢" if res['image']['label'] == "Real" else "🔴"
        img_class = "image-real" if res['image']['label'] == "Real" else "image-fake"
        st.markdown(f"""
        <div class="result-card {img_class}">
            <div class="icon">{img_icon}</div>
            <div><strong>Image Analysis</strong></div>
            <div>Prediction: <strong>{res['image']['label']}</strong></div>
            <div>Confidence: {res['image']['conf']:.2%}</div>
        </div>
        """, unsafe_allow_html=True)

    if uploaded_image:
        st.markdown("<div class='uploaded-image'>", unsafe_allow_html=True)
        st.image(uploaded_image, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='footer'>Made by Sadik Al Jarif</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
