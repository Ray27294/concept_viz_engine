# concept_viz_engine
A Web-based Data Visualisation System driven by Conceptual Modelling and Grammar of Graphics.

## To run the application locally

Before you start, ensure you have the following installed on your machine:
- **Python** (3.8 or higher)
- **Node.js** (v14 or higher) and npm

**1. Clone the repository:**
```bash
git clone https://github.com/Ray27294/concept_viz_engine.git
```

**2. Setup Backend:**

Make sure you are in the root directory of the project and run the following commands:

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment (For Windows)
venv\Scripts\activate

# Install backend dependencies
pip install -r requirements.txt

cd ..
```

**3. Setup Frontend:**

Make sure you are in the root directory of the project and run the following commands:
```bash
cd frontend
npm install
cd ..
```

**4. Run the application:**

Make sure your virtual environment is activated, then run the following command in the root directory of the project:
```bash
python run.py
```
The Backend will start at: http://127.0.0.1:8000

The Frontend will start at: http://localhost:5173

Open the frontend URL (http://localhost:5173) in a web browser and the application should be accesible.
