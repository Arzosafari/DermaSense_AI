# DermaSense AI 🩺🤖

**DermaSense AI** is a multimodal AI healthcare assistant for **skin lesion analysis and medical information retrieval**. The system combines a **Multi-Agent architecture, Large Language Models (LLMs), Retrieval-Augmented Generation (RAG), and a fine-tuned PanDerm Vision Transformer** to provide explainable and context-aware assistance.

## ✨ Features

* 🧠 Multi-Agent architecture for specialized healthcare tasks
* 🖼️ Skin lesion classification using a fine-tuned PanDerm ViT
* 🔍 Explainable AI with Attention Rollout heatmaps and ABCDE analysis
* 📚 RAG-based medical knowledge retrieval using FAISS
* 💬 LLM-powered medical conversation and reasoning
* 🩺 Symptom–disease matching
* 📄 Automatic PDF analysis reports
* 📊 Analysis history and system metrics
* 🔐 Token-based authentication

## 🏗️ Architecture

```text
User
  ↓
AgentOrchestrator
  ↓
 ├── Conversation Agent
 ├── Decider Agent
 ├── Disease Information Agent
 ├── Symptom Matcher Agent
 ├── Reasoning Agent
 └── Image Analysis Agent
          ↓
      PanDerm ViT
          ↓
 Classification + Risk Analysis
          ↓
 Attention Rollout + ABCDE Analysis
```

The RAG components retrieve relevant biomedical information and provide supporting context for the LLM's textual responses.

## 🧠 Skin Lesion Classification

The image analysis module uses a **PanDerm Vision Transformer** fine-tuned for an **8-class skin lesion classification task**.

### Training Configuration

* Batch Size: `128`
* Learning Rate: `5e-4`
* Epochs: `25`
* Warmup Epochs: `3`
* Weight Decay: `0.05`
* Layer Decay: `0.65`
* Drop Path: `0.2`
* Mixup: `0.8`
* CutMix: `1.0`
* Seed: `0`

### Results

| Metric            |     Score |
| ----------------- | --------: |
| Balanced Accuracy | **0.819** |
| AUC-ROC           | **0.968** |

The model was evaluated across dermoscopic and clinical image domains to address domain shift between different image sources.

## 📚 Datasets

The project uses:

* **ISIC 2019** — Dermoscopic skin lesion images
* **PAD-UFES-20** — Clinical smartphone skin lesion images
* A complementary multi-class skin lesion dataset

> Dataset ownership and usage rights remain with their respective providers.

## 🔎 Medical RAG

The medical knowledge retrieval module uses **FAISS** to retrieve relevant biomedical information from trusted sources, including:

* American Academy of Dermatology (AAD)
* DermNet
* NHS
* NICE

RAG is used to **ground the LLM's textual responses** and does not validate the accuracy of the image classification model.

## 🛠️ Tech Stack

**Backend**

* Python
* FastAPI

**AI / ML**

* PyTorch
* PanDerm
* Vision Transformers
* Large Language Models
* RAG
* FAISS

**Frontend & System**

* React
* TypeScript
* Multi-Agent Architecture
* Token-based Authentication
* PDF Report Generation

## 📁 Project Structure

```text
DermaSense_AI/
├── backend/
├── frontend/
├── docs/
├── external/
├── scripts/
├── tests/
├── .github/
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── README.md
└── LICENSE
```

## 📦 Large Files & Local Models

To keep the repository lightweight and suitable for GitHub, **large model files and local environments are intentionally excluded from this repository**.

The following are not included in GitHub:

* PanDerm model checkpoints
* Fine-tuned `.pth` model files
* Biomedical NER model files
* `all-MiniLM-L6-v2` model files
* Python virtual environments
* Node.js `node_modules`
* Other large binary/model files

These files remain available in the local development environment and are excluded using `.gitignore`.

If you want to reproduce the complete system, the required models should be **downloaded or obtained separately** and placed in their expected directories.

## ⚠️ Disclaimer

DermaSense AI is an **academic research project** and is not intended to provide medical diagnosis or replace professional medical advice.

## 📄 License

This project is licensed under the **MIT License**.

Third-party models, datasets, libraries, and other resources remain subject to their respective licenses.

## 👩‍💻 Authors

**Arezoo Safari & Mahsa Arjmandfar**

Bachelor's Research Project
**Zanjan University**
