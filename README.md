# RFP Matcher — Quick Start

This small app finds the best product matches for an RFP using a weighted matching algorithm and displays results in Streamlit.

What this README contains
- Quick prerequisites and install steps
- How to run the Streamlit UI on Windows PowerShell
- How to enable colored Match Score styling (optional matplotlib)
- Where to add a screenshot of the colored table

## Prerequisites
- Python 3.8+ (recommended)
- A virtual environment is recommended (venv, conda, etc.)

## Install dependencies
From the project root (where `requirements.txt` sits) run in PowerShell:

```powershell
python -m pip install -r .\requirements.txt
```

If you only want the minimal set but not the optional plotting/coloring support, you may install only `streamlit` and `pandas`:

```powershell
python -m pip install streamlit pandas
```

To enable the colored Match Score column in the main results table, install `matplotlib` (it's optional but recommended):

```powershell
python -m pip install matplotlib
```

## Run the app (Streamlit)

From PowerShell in the project folder:

```powershell
python -m streamlit run .\app.py
```

The UI will open in your browser. Click the "Analyze RFP" button to run the matching algorithm and view results.

## Screenshot (placeholder)
Below is a placeholder image showing how the colored Match Score table looks. Replace `assets/match_table_example.png` with an actual screenshot you generate from your Streamlit session.

![Colored Match Score example](assets/match_table_example.png)

To capture a screenshot:
- Run the app locally and open the results in your browser.
- Use your OS screenshot tool (Windows: Snipping Tool or PrtSc) and save the image as `assets/match_table_example.png`.

## Troubleshooting
- If Streamlit fails to start, ensure your Python executable is on PATH or run the `python -m streamlit ...` command exactly as shown.
- If you see the message in the UI saying `Optional package 'matplotlib' is not installed`, install it with:

```powershell
python -m pip install matplotlib
```

- If the main table looks unstyled after installation, restart the Streamlit server so the newly installed package is picked up.

## Files changed/added
- `README.md` — (this file) quick-run instructions and notes.
- `requirements.txt` — created earlier to list dependencies including `matplotlib` (optional).

If you want, I can:
- Add a short `Makefile` or PowerShell script (`run.ps1`) to automate setup/run steps.
- Generate and embed a real screenshot using a headless browser if you want an example image included automatically.

Happy to add any of those — which would you like next?