import requests
import os
import os
import PyPDF2
import sys

from utils import get_file_contents

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnableParallel
from operator import itemgetter
from langchain_core.callbacks import BaseCallbackHandler
# We can do the same thing with a SQLite cache
from langchain.cache import SQLiteCache
from langchain.globals import set_llm_cache


set_llm_cache(SQLiteCache(database_path=".langchain.db"))


from bs4 import BeautifulSoup

class Agent:
    def __init__(self, company_url):
        self.url = company_url
        print(f"Analysing {company_url}")
        self.company = company_url.split("company/")[-1].split("/")[0]
        print(f"Company: {self.company}")

        #define llm
        self.llm = AzureChatOpenAI(openai_api_version="2023-07-01-preview",
                                    azure_deployment="auto-test-turbo",temperature=0.0)
        
    def get_chain(self, system_prompt_filepath, human_prompt_filepath):
        # Get a basic chain with a prompt, llm and string parser

        system_prompt_content = get_file_contents(system_prompt_filepath)
        human_prompt_filepath = get_file_contents(human_prompt_filepath)

        chat_template = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt_content),
                ("human", human_prompt_filepath)
            ]
        )

        chain = chat_template | self.llm | StrOutputParser()

        return chain
    
    def get_concall_transcripts(self):
        # create a folder named after the company
        if not os.path.exists(self.company):
            os.makedirs(self.company)

        response = requests.get(self.url)
        if response.status_code == 200:
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")
            concall_links = soup.find_all(class_="concall-link")
            href_links = []
            for link in concall_links:
                if link.text.strip()=='Transcript' and link.get("href")!=None:
                    href_links.append(link.get("href"))
            print(f"Found {len(href_links)} concall transcripts for {self.company}")
            # create a folder named concall inside the company directory
            if not os.path.exists(os.path.join(self.company, "concall")):
                os.makedirs(os.path.join(self.company, "concall"))
            # download the pdf files to the concall folder
            for link in href_links:
                pdf_link = link
                pdf_file = pdf_link.split("/")[-1]
                output_file = os.path.join(self.company, "concall", pdf_file)
                # check if the file already exists
                if os.path.exists(output_file):
                    print(f"File {pdf_file} already exists for {self.company}")
                    continue
                os.system(f"wget -O {output_file} {pdf_link}")
                print(f"Downloaded {pdf_file} to {self.company}")
        else:
            print("Failed to fetch HTML content. Status code:", response.status_code)

    def get_pdf_text(self, pdf_file):
        with open(pdf_file, 'rb') as file:
            # if unable to read the pdf file, return an empty string
            try:
                pdf_reader = PyPDF2.PdfReader(file)
            except Exception as e:
                return None
            text = ''
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text()
            return text
        
    def get_summary(self, pdf_file):
        #create a folder named summary inside the company directory
        if not os.path.exists(os.path.join(self.company, "summary")):
            os.makedirs(os.path.join(self.company, "summary"))
        
        # for each pdf file, extract the text and generate a summary, check if the summary already exists, if not generate a new one
        summary_file = os.path.join(self.company, "summary", pdf_file.split("/")[-1].replace(".pdf", ".txt"))
        if os.path.exists(summary_file):
            print(f"Summary already exists for {pdf_file}")
            with open(summary_file, 'r') as file:
                return file.read()
        print(f'Extracting text from {pdf_file}')
        concall = self.get_pdf_text(pdf_file)
        if not concall:
            print(f"Failed to extract text from {pdf_file}")
            return ""
        print("Generating Summaries\n")
        summary_chain = self.get_chain("./prompts/system_prompt.md", "./prompts/summary_prompt.md")
        summary_iter = summary_chain.stream({"concall_discussion" : concall})
        summary = ""
        for chunk in summary_iter:
            print(chunk, end="", flush=True)
            summary += chunk
        with open(summary_file, 'w') as file:
            file.write(summary)
        return summary

    def summarise_concalls(self):
        self.get_concall_transcripts()
        # for each concall transcript, generate a summary
        concall_folder = os.path.join(self.company, "concall")
        pdf_files = [os.path.join(concall_folder, file) for file in os.listdir(concall_folder) if file.endswith(".pdf")]
        summaries = []
        for pdf_file in pdf_files:
            print(f"Summarising {pdf_file}")
            summary = self.get_summary(pdf_file)
            summaries.append(summary)
        complete_summary = " ".join(summaries)
        self.concall_summary = complete_summary
    
    def analyse_concalls(self):
        # create a folder named analysis inside the company directory
        if not os.path.exists(os.path.join(self.company, "analysis")):
            os.makedirs(os.path.join(self.company, "analysis"))
        # analyse the concall summary
        # check if the analysis already exists, if not generate a new one
        analysis_file = os.path.join(self.company, "analysis", "concall_analysis.md")
        if os.path.exists(analysis_file):
            print(f"Analysis already exists for {self.company}")
            self.concall_analysis = get_file_contents(analysis_file)
            return
        print("Analysing Concall Summary\n")
        analysis_chain = self.get_chain("./prompts/system_prompt.md", "./prompts/concall_analysis_prompt.md")
        analysis_iter = analysis_chain.stream({"full_summary" : self.concall_summary})
        analysis = ""
        for chunk in analysis_iter:
            print(chunk, end="", flush=True)
            analysis += chunk
        print("\n")
        self.concall_analysis = analysis
        with open(analysis_file, 'w') as file:
            file.write(analysis)

    def extract_table(self, id):
        response = requests.get(self.url)
        if response.status_code == 200:
            html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")
        quarters_section = soup.find('section', id=id)
        if quarters_section:
            table = quarters_section.find('table')
            if table:
                rows = table.find_all('tr')
                headers = [header.text.strip() for header in rows[0].find_all('th')]
                data = []
                for row in rows[1:]:
                    data.append([cell.text.strip() for cell in row.find_all('td')])
                # convert the header and data into a string
                headers = ','.join(headers)
                data = [','.join(row) for row in data]
                data = '\n'.join(data)
                # combine header and data into a single string and return
                return headers+'\n'+data
    def extract_numbers(self):
        self.quartely_data = self.extract_table('quarters')
        self.pnl_data = self.extract_table('profit-loss')
        self.balancesheet_data = self.extract_table('balance-sheet')
    
    def analyse(self):
        print("Analysing the company data\n")
        analysis_chain = self.get_chain("./prompts/system_prompt.md", "./prompts/analysis.md")
        analysis_iter = analysis_chain.stream({"company" : self.company, "quarterly_data" : self.quartely_data, "pnl_data" : self.pnl_data, "balance_sheet_data" : self.balancesheet_data, "concall_analysis" : self.concall_analysis})
        analysis = ""
        for chunk in analysis_iter:
            print(chunk, end="", flush=True)
            analysis += chunk
        print("\n")
        self.company_analysis = analysis
        # create a folder named analysis inside the company directory
        if not os.path.exists(os.path.join(self.company, "analysis")):
            os.makedirs(os.path.join(self.company, "analysis"))
        analysis_file = os.path.join(self.company, "analysis", "company_analysis.md")
        # if the analysis already exists skip the writing
        if not os.path.exists(analysis_file):
            with open(analysis_file, 'w') as file:
                file.write(analysis)
        else:
            print(f"Analysis already exists for {self.company}")
        self.analysis = analysis
if __name__ == "__main__":
    # Take url as sysarg
    url = sys.argv[1]
    agent = Agent(url)
    agent.summarise_concalls()
    agent.analyse_concalls()
    agent.extract_numbers()
    agent.analyse()


