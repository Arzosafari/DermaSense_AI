# DermaSense AI 🩺🤖

**DermaSense AI** is a multimodal AI research system for **skin lesion analysis and evidence-grounded medical information retrieval**. The project integrates **computer vision, large language models (LLMs), retrieval-augmented generation (RAG), and a multi-agent architecture** to explore explainable and context-aware AI assistance for dermatological image and symptom analysis.

The system combines a fine-tuned **PanDerm Vision Transformer** for skin lesion classification with specialized AI agents for symptom matching, medical information retrieval, reasoning, and conversational interaction.

> **Research project:** DermaSense AI was developed as a Bachelor's research project at **Zanjan University** by **Arezoo Safari and Mahsa Arjmandfar**.

---

## 🔬 Research Motivation

Dermatological image analysis involves several challenges, including:

* Variation between dermoscopic and clinical images
* Domain shift across image sources
* The need for interpretable visual predictions
* Combining image-based evidence with patient-provided symptoms
* Providing reliable medical information alongside model predictions

DermaSense AI explores a **multimodal and modular architecture** that combines visual analysis with symptom information and retrieval-grounded language generation.

The system is designed as a **research and decision-support prototype**, rather than an autonomous diagnostic system.

---

##  Key Features

*  **Multi-Agent Architecture** for specialized healthcare tasks
*  **Skin Lesion Classification** using a fine-tuned PanDerm Vision Transformer
*  **Explainable Visual Analysis** using Attention Rollout heatmaps
*  **ABCDE-based Risk Analysis** as an additional image-analysis component
*  **Out-of-Distribution (OOD) Analysis** to investigate model behavior on potentially unfamiliar inputs
*  **Retrieval-Augmented Generation (RAG)** for evidence-grounded medical information
*  **FAISS-based Biomedical Retrieval**
*  **LLM-powered Medical Conversation and Reasoning**
*  **Symptom–Disease Matching**
*  **Automatic PDF Analysis Reports**
*  **Analysis History and System Metrics**
*  **Token-based Authentication**

---

# 🏗️ System Architecture

```text
                              User
                               │
                               ▼
                       Agent Orchestrator
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
 Conversation Agent      Decider Agent       Image Analysis Agent
          │                    │                    │
          │                    │                    ▼
          │                    │              PanDerm ViT
          │                    │                    │
          │                    │          ┌─────────┴─────────┐
          │                    │          │                   │
          │                    │          ▼                   ▼
          │                    │   Classification      Risk Analysis
          │                    │          │                   │
          │                    │          └─────────┬─────────┘
          │                    │                    ▼
          │                    │          Attention Rollout
          │                    │                    │
          │                    │                    ▼
          │                    │              ABCDE Analysis
          │                    │
          ├────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
 Disease Information     Symptom Matcher       Reasoning Agent
      Agent                  Agent                  │
          │                    │                    │
          └────────────────────┼────────────────────┘
                               ▼
                         RAG / FAISS
                               │
                               ▼
                    Evidence-Grounded Context
                               │
                               ▼
                         LLM Response
```

The architecture separates image analysis, symptom interpretation, information retrieval, reasoning, and conversation into specialized components.

This modular design allows individual components to be developed and evaluated independently while enabling them to work together through the central agent orchestrator.

---

# 🧠 Skin Lesion Classification

The image analysis module uses a **PanDerm Vision Transformer** fine-tuned for an **8-class skin lesion classification task**.

### Training Configuration

| Parameter     |  Value |
| ------------- | -----: |
| Batch Size    |  `128` |
| Learning Rate | `5e-4` |
| Epochs        |   `25` |
| Warmup Epochs |    `3` |
| Weight Decay  | `0.05` |
| Layer Decay   | `0.65` |
| Drop Path     |  `0.2` |
| Mixup         |  `0.8` |
| CutMix        |  `1.0` |
| Seed          |    `0` |

### Evaluation Results

| Metric            |     Score |
| ----------------- | --------: |
| Balanced Accuracy | **0.819** |
| AUC-ROC           | **0.968** |

The evaluation includes images from both **dermoscopic and clinical image domains**, allowing the project to investigate model behavior under differences in image acquisition and domain characteristics.

These metrics describe the performance of the implemented classification model on the project's evaluation setup and should not be interpreted as clinical diagnostic performance.

---

# 🔍 Explainability and Risk Analysis

DermaSense AI incorporates several complementary analysis components around the image classifier.

### Attention Rollout

Attention Rollout is used to visualize image regions that contribute to the model's attention patterns. These visualizations are intended to improve interpretability and provide additional context when examining model predictions.

### ABCDE Analysis

The system incorporates an automated analysis based on the commonly used **ABCDE framework**:

* **A — Asymmetry**
* **B — Border**
* **C — Color**
* **D — Diameter**
* **E — Evolution**

The ABCDE component is treated as an additional analytical signal rather than a standalone diagnostic method.

### Out-of-Distribution Analysis

OOD analysis is incorporated to investigate whether an input may differ substantially from the data distribution encountered during model development.

This component is intended to provide an additional signal for identifying potentially unfamiliar inputs rather than guaranteeing that an image is medically valid or clinically interpretable.

---

# 📚 Medical Knowledge Retrieval

The medical information component uses **Retrieval-Augmented Generation (RAG)** with **FAISS** to retrieve relevant biomedical information before generating textual responses.

The retrieval layer is designed to ground responses in external medical references rather than relying exclusively on the language model's parametric knowledge.

### Reference Sources

The project incorporates information from sources including:

* [American Academy of Dermatology (AAD)](https://www.aad.org/)
* [DermNet](https://dermnetnz.org/)
* [NHS](https://www.nhs.uk/)
* [NICE](https://www.nice.org.uk/)

> RAG retrieval provides supporting context for textual responses. It does **not** validate, calibrate, or guarantee the correctness of the image classification model.

---

# 🤖 Multi-Agent System

DermaSense AI uses specialized agents to separate different healthcare-oriented tasks.

### Conversation Agent

Handles user interaction and maintains conversational context.

### Decider Agent

Determines which processing path or combination of agents is appropriate for a given request.

### Image Analysis Agent

Processes skin images using the fine-tuned PanDerm model and associated visual analysis components.

### Symptom Matcher Agent

Matches user-provided symptoms with relevant disease information.

### Disease Information Agent

Retrieves and presents relevant medical information.

### Reasoning Agent

Combines available information and produces structured reasoning for the response pipeline.

---

# 📊 Multimodal Processing

A central objective of the project is to combine multiple information modalities rather than relying solely on image classification.

The system can integrate:

```text
Skin Image
    +
User Symptoms
    +
Retrieved Medical Knowledge
    +
LLM Reasoning
    ↓
Context-Aware AI Response
```

This architecture allows the project to explore how visual information, structured symptom information, and retrieved biomedical knowledge can work together within an AI-assisted healthcare workflow.

---

# 📁 Datasets

The project uses datasets including:

* **ISIC 2019** — Dermoscopic skin lesion images
* **PAD-UFES-20** — Clinical smartphone skin lesion images
* A complementary multi-class skin lesion dataset

Dataset ownership, access conditions, and usage rights remain with their respective providers.

---

# 🛠️ Technology Stack

### Backend

* Python
* FastAPI

### AI / Machine Learning

* PyTorch
* PanDerm
* Vision Transformers
* Large Language Models (LLMs)
* Retrieval-Augmented Generation (RAG)
* FAISS

### Frontend & System

* React
* TypeScript
* Multi-Agent Architecture
* Token-based Authentication
* PDF Report Generation

---

# 📁 Project Structure

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

---

# 📦 Large Files and Local Models

To keep the repository lightweight and suitable for GitHub, large model checkpoints and local environments are intentionally excluded.

The following resources are not included in the repository:

* PanDerm model checkpoints
* Fine-tuned `.pth` model files
* Biomedical NER model files
* `all-MiniLM-L6-v2` model files
* Python virtual environments
* Node.js `node_modules`
* Other large binary/model files

These resources remain available in the local development environment and are excluded through `.gitignore`.

For full reproduction, the required models and resources must be obtained separately and placed in their expected directories.

---

# 🧪 Research Scope

DermaSense AI is primarily intended to explore the integration of:

**Computer Vision + Medical AI + LLMs + RAG + Multi-Agent Systems**

The project focuses on the engineering and research challenges involved in combining these components into a single multimodal healthcare-oriented system.

Potential research directions include:

* Robustness across clinical and dermoscopic image domains
* Explainable medical image analysis
* Multimodal AI for dermatological assistance
* Retrieval-grounded medical language generation
* Out-of-distribution detection
* Agent-based healthcare architectures

---

# ⚠️ Disclaimer

**DermaSense AI is an academic research project and experimental decision-support prototype.**

It is **not intended to provide medical diagnosis, replace a dermatologist or other healthcare professional, or be used as a standalone clinical decision-making system.**

Model predictions and generated responses may contain errors and should not be interpreted as medical advice.

---

# 📌 Project Attribution

DermaSense AI builds upon the initial structure of the **SmartHealth-LLM** project.

The original SmartHealth-LLM structure served as the starting point for the project, after which the system was substantially **extended, modified, and developed** to create the current DermaSense AI architecture.

The current project includes additional components and integrations, including:

* Fine-tuned PanDerm-based image analysis
* Multi-agent orchestration
* Skin lesion classification
* Attention Rollout visualization
* ABCDE analysis
* OOD analysis
* Medical RAG and FAISS retrieval
* Symptom–disease matching
* LLM-based reasoning and conversation
* PDF report generation
* Authentication and system management

The attribution to the original **SmartHealth-LLM** project is retained to acknowledge the project's development history and initial structural foundation.

---

# 👩‍💻 Authors

**Arezoo Safari & Mahsa Arjmandfar**

Bachelor's Research Project
**University of Zanjan**

---

## 📄 License

This project is licensed under the **MIT License**.

Third-party models, datasets, libraries, medical resources, and other external components remain subject to their respective licenses.
