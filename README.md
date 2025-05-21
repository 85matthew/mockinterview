# Live Interview Simulator

This program uses the Google Generative AI Live API to conduct a practice interview.

## Setup

1.  **Clone the repository (or download the files).**
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set up Environment Variables:**
    Create a `.env` file in the project root with the following content, replacing the placeholder values with your actual Google Cloud project details:

    ```env
    GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    GOOGLE_CLOUD_LOCATION="your-gcp-location" # e.g., "us-central1" or "global"
    # GOOGLE_API_KEY="your-google-api-key" # Only if not using Application Default Credentials
    ```
    Ensure `GOOGLE_GENAI_USE_VERTEXAI=True` is set in your environment if you are using Vertex AI. You can set this in your shell environment or potentially within the Python script using `os.environ`.

    For authentication, this application will attempt to use Application Default Credentials (ADC) if a `GOOGLE_API_KEY` is not explicitly provided. Ensure your ADC is configured correctly if you choose this path (e.g., by running `gcloud auth application-default login`).

## Usage

```bash
python interview_simulator.py
```

The script will then guide you through the interview process.
