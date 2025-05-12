import json
import re
import csv # Modul für CSV-Operationen importieren
from bs4 import BeautifulSoup

# Die HTML-Datei einlesen
try:
    with open('indeed.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
except FileNotFoundError:
    print("Fehler: indeed.html nicht gefunden. Bitte stellen Sie sicher, dass die Datei existiert.")
    exit()

soup = BeautifulSoup(html_content, 'html.parser')

initial_data_script_content = None
for script_tag in soup.find_all('script'):
    if script_tag.string and 'window._initialData' in script_tag.string:
        initial_data_script_content = script_tag.string
        break

jobs = []
base_url = "https://de.indeed.com"
processed_job_keys = set()

def extract_json_object_from_script(script_content, variable_name="window._initialData"):
    try:
        start_index = script_content.find(f"{variable_name}")
        if start_index == -1:
            return None
        
        json_start_index = script_content.find('{', start_index)
        if json_start_index == -1:
            return None

        open_braces = 0
        json_end_index = -1
        for i in range(json_start_index, len(script_content)):
            if script_content[i] == '{':
                open_braces += 1
            elif script_content[i] == '}':
                open_braces -= 1
                if open_braces == 0:
                    json_end_index = i + 1
                    break
        
        if json_end_index != -1:
            return script_content[json_start_index:json_end_index]
        else: 
            match = re.search(r"window\._initialData\s*=\s*(\{.*\});", script_content, re.DOTALL | re.MULTILINE)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Fehler bei der JSON-Extraktionslogik: {e}")
    return None


if initial_data_script_content:
    print("Daten aus window._initialData gefunden. Verarbeite...")
    
    json_str = extract_json_object_from_script(initial_data_script_content)
    
    if json_str:
        try:
            data = json.loads(json_str)
            
            job_cards_list_data = data.get('mosaicData', {}).get('providerData', {}).get('mosaic-provider-jobcards', {}).get('metaData', {}).get('mosaicProviderJobCardsModel', {}).get('results', [])
            auto_open_job_data_container = data.get('autoOpenTwoPaneViewjobResponse', {}).get('body', {}).get('hostQueryExecutionResult', {}).get('data', {}).get('jobData', {}).get('results', [])

            if auto_open_job_data_container:
                job_detail_wrapper = auto_open_job_data_container[0]
                job_detail = job_detail_wrapper.get('job', {})
                job_key = job_detail.get('key')

                if job_key and job_key not in processed_job_keys:
                    title = job_detail.get('title')
                    company = job_detail.get('sourceEmployerName') or job_detail.get('employer', {}).get('name')
                    location_obj = job_detail.get('location', {})
                    location = location_obj.get('formatted', {}).get('long') or location_obj.get('city') or location_obj.get('fullAddress')
                    description_html = job_detail.get('description', {}).get('html')
                    snippet_text = "N/A"
                    if description_html:
                        desc_soup = BeautifulSoup(description_html, 'html.parser')
                        snippet_text = desc_soup.get_text(separator=' ', strip=True)[:250] + "..."
                    
                    raw_link = job_detail.get('url') 
                    link = raw_link if raw_link and not raw_link.startswith("/") else (base_url + raw_link if raw_link else f"{base_url}/viewjob?jk={job_key}")

                    jobs.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'snippet': snippet_text,
                        'link': link,
                        'source': 'autoOpenJobDetail'
                    })
                    processed_job_keys.add(job_key)

            if job_cards_list_data:
                for job_card_data in job_cards_list_data:
                    job_key = job_card_data.get('jobkey')
                    if job_key and job_key not in processed_job_keys:
                        title = job_card_data.get('displayTitle') or job_card_data.get('title')
                        company = job_card_data.get('company')
                        location = job_card_data.get('formattedLocation')
                        snippet_html = job_card_data.get('snippet')
                        snippet_text = "N/A"
                        if snippet_html:
                            snippet_soup = BeautifulSoup(snippet_html, 'html.parser')
                            snippet_text = snippet_soup.get_text(separator=' ', strip=True)
                        
                        relative_link = job_card_data.get('link')
                        link = base_url + relative_link if relative_link and relative_link.startswith('/') else (relative_link or f"{base_url}/viewjob?jk={job_key}")

                        jobs.append({
                            'title': title,
                            'company': company,
                            'location': location,
                            'snippet': snippet_text,
                            'link': link,
                            'source': 'jobCardList'
                        })
                        processed_job_keys.add(job_key)
            elif not auto_open_job_data_container:
                 print("Keine Job-Daten in den erwarteten JSON-Pfaden ('mosaicProviderJobCardsModel' oder 'autoOpenTwoPaneViewjobResponse') gefunden.")

        except json.JSONDecodeError as e:
            print(f"Fehler beim Parsen von JSON aus _initialData: {e}")
            error_pos = getattr(e, 'pos', None)
            if error_pos is not None:
                start = max(0, error_pos - 250)
                end = min(len(json_str), error_pos + 250)
                print(f"Problematischer JSON-Ausschnitt (um Position {error_pos}):\n---\n{json_str[start:end]}\n---")
            else:
                print("Der JSON-String konnte nicht geladen werden. Hier sind die ersten und letzten 500 Zeichen:")
                print(f"Anfang: {json_str[:500]}")
                print(f"Ende: {json_str[-500:]}")
        except Exception as e:
            print(f"Allgemeiner Fehler beim Verarbeiten von _initialData: {e}")
    else:
        print("Konnte das JSON-Objekt in window._initialData mit der Extraktionslogik nicht finden.")

if not jobs:
    print("Keine Jobs aus _initialData extrahiert. Versuche klassisches HTML-Parsing (weniger zuverlässig)...")
    job_cards_html = soup.select('li.css-1ac2h1w div.cardOutline')
    if not job_cards_html:
        job_cards_html = soup.find_all('li', class_='css-1ac2h1w')

    for card in job_cards_html:
        title_tag_outer = card.find('h2', class_='jobTitle')
        title_tag = title_tag_outer.find('a') if title_tag_outer else None
        title = title_tag.get_text(strip=True).replace('\n', ' ').strip() if title_tag else "N/A"
        
        link = "N/A"
        if title_tag and title_tag.has_attr('href'):
            relative_link = title_tag['href']
            if relative_link.startswith("/pagead/clk"):
                jk_match = re.search(r'[?&]jk=([a-f0-9]+)', relative_link)
                if jk_match:
                    link = f"{base_url}/viewjob?jk={jk_match.group(1)}"
                else:
                    link = base_url + relative_link
            elif relative_link.startswith("/"):
                link = base_url + relative_link
            else:
                link = relative_link
        
        company_tag = card.find('span', attrs={'data-testid': 'company-name'})
        company = company_tag.get_text(strip=True) if company_tag else "N/A"
        
        location_tag = card.find('div', attrs={'data-testid': 'text-location'})
        location = location_tag.get_text(strip=True) if location_tag else "N/A"
        
        snippet_items_texts = []
        snippet_div = card.find('div', attrs={'data-testid': 'jobsnippet_footer'})
        if snippet_div:
            for li_tag in snippet_div.find_all('li'):
                snippet_items_texts.append(li_tag.get_text(strip=True))
            
            for child_node in snippet_div.children:
                if child_node.name not in ['ul', 'div'] and isinstance(child_node, str):
                    text_content = child_node.strip()
                    if text_content and "Anzeige" not in text_content and not re.search(r'(Gespeichert|Angesehen) vor \d+ \w+', text_content):
                        snippet_items_texts.append(text_content)
                elif child_node.name == 'span' and not child_node.find_parent('ul'):
                    text_content = child_node.get_text(strip=True)
                    if text_content and "Anzeige" not in text_content and not re.search(r'(Gespeichert|Angesehen) vor \d+ \w+', text_content):
                         if child_node.get('data-testid') != "myJobsState":
                            snippet_items_texts.append(text_content)

        snippet_text = " ".join(filter(None, snippet_items_texts)).strip() or "N/A"

        if title != "N/A":
            job_key_html = ""
            if title_tag and title_tag.has_attr('id'):
                id_parts = title_tag['id'].split('_')
                if len(id_parts) > 1:
                    job_key_html = id_parts[-1]
            
            if job_key_html and job_key_html in processed_job_keys:
                continue
            
            jobs.append({
                'title': title,
                'company': company,
                'location': location,
                'snippet': snippet_text,
                'link': link,
                'source': 'html_fallback'
            })
            if job_key_html:
                processed_job_keys.add(job_key_html)

# Deduplizierung und Ausgabe
unique_jobs_output = []
seen_job_signatures = set()

for job_item in jobs:
    # Erstelle eine eindeutige Signatur (Titel und Firma könnten ausreichen, Link ist besser)
    # Normalisiere für bessere Duplikaterkennung
    title_norm = job_item.get('title', 'n/a').lower().strip()
    company_norm = job_item.get('company', 'n/a').lower().strip()
    # Link ist oft der beste eindeutige Identifikator, wenn er nicht 'N/A' ist
    link_norm = job_item.get('link', 'n/a').lower().strip()
    
    signature = (title_norm, company_norm, link_norm if link_norm != "n/a" else (title_norm + company_norm)) # Fallback für Signatur, falls Link N/A
    
    if signature not in seen_job_signatures:
        unique_jobs_output.append(job_item)
        seen_job_signatures.add(signature)

if unique_jobs_output:
    print(f"\n{len(unique_jobs_output)} eindeutige Jobs gefunden:\n")
    for i, job in enumerate(unique_jobs_output):
        print(f"--- Job {i+1} ---")
        print(f"Titel: {job.get('title')}")
        print(f"Unternehmen: {job.get('company')}")
        print(f"Ort: {job.get('location')}")
        print(f"Snippet: {job.get('snippet')}")
        print(f"Link: {job.get('link')}")
        # print(f"Quelle: {job.get('source')}") 
    print("-" * 20)

    # In CSV speichern
    csv_file_name = 'indeed_jobs.csv'
    csv_columns = ['title', 'company', 'location', 'snippet', 'link', 'source']
    try:
        with open(csv_file_name, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            for job_data in unique_jobs_output:
                # Stelle sicher, dass alle Spalten im Wörterbuch vorhanden sind, um Fehler zu vermeiden
                row_to_write = {col: job_data.get(col, '') for col in csv_columns}
                writer.writerow(row_to_write)
        print(f"Daten erfolgreich in '{csv_file_name}' gespeichert.")
    except IOError:
        print(f"Fehler beim Schreiben der CSV-Datei '{csv_file_name}'.")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist beim CSV-Export aufgetreten: {e}")

else:
    print("Keine Jobs gefunden.")