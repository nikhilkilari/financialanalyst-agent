# financialanalyst-agent
Smart agent to analyse a company based on the data present in the screener.in website

## Environment Setup:
**Required**
```
export OPENAI_API_VERSION=""
export AZURE_OPENAI_ENDPOINT=""
export AZURE_OPENAI_API_KEY=""
```

## Usage:
```
python3 langchain_main.py "URL"
```

## Sample Usage:
```
python3 langchain_main.py "https://www.screener.in/company/HDFCBANK/consolidated/"
```