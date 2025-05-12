from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin

# Pfad zur lokalen HTML-Datei
HTML_FILE_PATH = 'view-source_https___de.indeed.com_jobs_q=Ai+Engineer&l=Berlin&radius=25&vjk=478dc54de061badf&advn=233499551656184.html'
BASE_URL = "https://de.indeed.com/" # Basis-URL für relative Links

csv_filename = 'indeed_ai_engineer_berlin_local.csv'
csv_headers = ['Arbeitgeber', 'PLZ', 'Link']
jobs_data = []

try:
    # HTML-Datei öffnen und lesen
    with open(HTML_FILE_PATH, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Alle Listenelemente finden, die Jobkarten enthalten
    # Die Klasse 'css-1ac2h1w' scheint für <li> Elemente zu sein, die Jobkarten umschließen
    job_cards_containers = soup.find_all('li', class_='css-1ac2h1w') 
    
    if not job_cards_containers:
        print("Keine Job-Container mit der Klasse 'css-1ac2h1w' gefunden. Überprüfen Sie die Selektoren oder das HTML-Dokument.")

    for container in job_cards_containers:
        # Jedes <li> Element kann eine Jobkarte oder anderen Inhalt haben.
        # Wir suchen nach typischen Jobkarten-Strukturen (z.B. mit 'cardOutline')
        job_card = container.find('div', class_=lambda x: x and 'cardOutline' in x.split())
        if not job_card: # Wenn es kein div mit 'cardOutline' ist, könnte es ein anderer li-Typ sein (z.B. Mosaic-Platzhalter)
            continue

        arbeitgeber_tag = job_card.find('span', attrs={'data-testid': 'company-name'})
        arbeitgeber = arbeitgeber_tag.text.strip() if arbeitgeber_tag else 'N/A'

        standort_tag = job_card.find('div', attrs={'data-testid': 'text-location'})
        standort_text = standort_tag.text.strip() if standort_tag else 'N/A'
        
        plz = 'N/A'
        # Versuche, eine 5-stellige PLZ zu finden
        plz_match = re.search(r'\b\d{5}\b', standort_text)
        if plz_match:
            plz = plz_match.group(0)
        elif "Homeoffice" in standort_text and "Berlin" in standort_text:
            plz = "Homeoffice (Berlin)" # Spezifischer für Berlin
        elif "Deutschland" in standort_text and not plz_match: # Fallback, wenn nur "Deutschland" da steht
             plz = "Deutschland (Keine PLZ)"
        elif "Homeoffice" in standort_text: # Allgemeiner Homeoffice-Fallback
            plz = "Homeoffice"
        

        link_tag = job_card.find('a', class_='jcs-JobTitle') # Oft die Klasse für den Jobtitel-Link
        job_link = 'N/A'
        if link_tag and link_tag.get('href'):
            relative_link = link_tag['href']
            # Stelle sicher, dass relative Links korrekt mit der Basis-URL verbunden werden
            if relative_link.startswith('/'):
                job_link = urljoin(BASE_URL, relative_link)
            else: # Falls es bereits ein absoluter Link ist (unwahrscheinlich im Snippet, aber sicher ist sicher)
                job_link = relative_link
        
        # Nur Jobs mit Arbeitgeber und Link hinzufügen, um leere Einträge zu vermeiden
        if arbeitgeber != 'N/A' and job_link != 'N/A':
            jobs_data.append({
                'Arbeitgeber': arbeitgeber,
                'PLZ': plz,
                'Link': job_link
            })
    
    print(f"Insgesamt {len(jobs_data)} Jobs gefunden und verarbeitet.")

except FileNotFoundError:
    print(f"Fehler: Die Datei '{HTML_FILE_PATH}' wurde nicht gefunden.")
except Exception as e:
    print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")

if jobs_data:
    try:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            for job in jobs_data:
                writer.writerow(job)
        print(f"Daten erfolgreich in '{csv_filename}' gespeichert.")
    except IOError:
        print(f"Fehler beim Schreiben der CSV-Datei '{csv_filename}'.")
else:
    print("Keine Jobdaten zum Schreiben in die CSV-Datei gefunden.")