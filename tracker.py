import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
# import matplotlib.dates as mdates # Not strictly used, can be removed if not needed
# from datetime import datetime # Not strictly used, can be removed if not needed
import os
import re
# import json # Not strictly used, can be removed if not needed

# --- For loading .env file for local development ---
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file if it exists
# ----------------------------------------------------

# --- Configuration ---
TEAM_ID = "372250"
TEAM_NAME = "Obsidian Howlers"
TEAM_PAGE_URL = f"https://ctftime.org/team/{TEAM_ID}"

# Secrets will be loaded from environment variables (either from .env locally or GitHub Secrets in Actions)

# --- Helper Functions ---
def get_event_id_from_url(event_url):
    """Extracts event ID from CTFtime event URL."""
    if not event_url:
        return None
    match = re.search(r'/event/(\d+)', event_url)
    return match.group(1) if match else None

def fetch_total_teams(event_url):
    """Fetches total number of teams for a given event."""
    if not event_url:
        print("  Cannot fetch total teams, event URL is missing.")
        return None
    try:
        print(f"  Fetching total teams from: {event_url}")
        response = requests.get(event_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        scoreboard_header = soup.find('h3', string='Scoreboard')
        if scoreboard_header:
            total_teams_p = scoreboard_header.find_next_sibling('p', align='right')
            if total_teams_p:
                match = re.search(r'(\d+)\s+teams\s+total', total_teams_p.text)
                if match:
                    total_teams_count = int(match.group(1))
                    print(f"    Found {total_teams_count} total teams.")
                    return total_teams_count
        
        total_teams_text_element = soup.find(string=re.compile(r'\d+\s+teams\s+total'))
        if total_teams_text_element:
            match = re.search(r'(\d+)\s+teams\s+total', total_teams_text_element)
            if match:
                total_teams_count = int(match.group(1))
                print(f"    Found {total_teams_count} total teams (fallback).")
                return total_teams_count
        
        print(f"    Could not find total teams text on {event_url}")

    except requests.RequestException as e:
        print(f"  Error fetching event page {event_url}: {e}")
    except Exception as e:
        print(f"  Error parsing event page {event_url}: {e}")
    return None

# --- Main Scraping Logic ---
def scrape_team_ctf_data():
    print(f"Scraping data for team ID: {TEAM_ID} from {TEAM_PAGE_URL}")
    try:
        response = requests.get(TEAM_PAGE_URL, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch team page: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    participated_ctfs = []

    h3_participated = soup.find('h3', string='Participated in CTF events')
    if not h3_participated:
        print("Could not find 'Participated in CTF events' section.")
        return []

    year_tab_links = h3_participated.find_next_sibling('ul', class_='nav-tabs').find_all('a')
    year_data_to_process = []

    for link in year_tab_links:
        year_str = link.get_text(strip=True)
        tab_id = link['href'].lstrip('#')
        if year_str.isdigit():
            year_data_to_process.append({'year': year_str, 'tab_id': tab_id})

    if not year_data_to_process:
        first_tab_content = h3_participated.find_next_sibling('div', class_='tab-content').find('div', class_='tab-pane')
        if first_tab_content:
            overall_rating_p = first_tab_content.find('p', string=re.compile(r'Overall rating place:.*?in\s+(\d{4})'))
            if overall_rating_p:
                year_match = re.search(r'in\s+(\d{4})', overall_rating_p.text)
                if year_match:
                     year_data_to_process.append({'year': year_match.group(1), 'tab_id': first_tab_content.get('id')})

    for year_info in year_data_to_process:
        year_str = year_info['year']
        tab_content_div_id = year_info['tab_id']
        
        print(f"Processing year: {year_str} (tab: {tab_content_div_id})")
        tab_content = soup.find('div', id=tab_content_div_id)

        if not tab_content:
            print(f"Could not find tab content for id: {tab_content_div_id}")
            continue

        table = tab_content.find('table', class_='table-striped')
        if not table:
            print(f"No participation table found for year {year_str}")
            continue

        rows = table.find_all('tr')
        if len(rows) <= 1:
            continue

        for row_idx, row in enumerate(rows[1:]):
            cols = row.find_all('td')
            if len(cols) == 5:
                try:
                    place = cols[1].text.strip()
                    event_link_tag = cols[2].find('a')
                    event_name = event_link_tag.text.strip() if event_link_tag else "N/A"
                    event_url_suffix = event_link_tag['href'] if event_link_tag else None
                    event_url = f"https://ctftime.org{event_url_suffix}" if event_url_suffix else None
                    event_id = get_event_id_from_url(event_url)
                    ctf_points_text = cols[3].text.strip()
                    rating_points_text = cols[4].text.strip().replace('*', '')

                    ctf_points_value = 0.0
                    try:
                        ctf_points_value = float(ctf_points_text) if ctf_points_text else 0.0
                    except ValueError:
                        print(f"  Warning: Could not parse CTF points '{ctf_points_text}' for {event_name}. Using 0.0.")

                    rating_points_value = 0.0
                    try:
                        rating_points_value = float(rating_points_text) if rating_points_text else 0.0
                    except ValueError:
                        print(f"  Warning: Could not parse Rating points '{rating_points_text}' for {event_name}. Using 0.0.")

                    total_teams_data = fetch_total_teams(event_url) if (event_id and event_name != "N/A") else 'N/A'
                    total_teams = total_teams_data or 'N/A'


                    rank_percentile = 'N/A'
                    if isinstance(total_teams, int) and place.isdigit():
                        if total_teams > 0:
                            rank_percentile = round((int(place) / total_teams) * 100, 2)
                        else:
                            rank_percentile = 'N/A'

                    participated_ctfs.append({
                        'Year': year_str,
                        'Event Name': event_name,
                        'Event ID': event_id if event_id else 'N/A',
                        'Your Rank': place if place else 'N/A',
                        'Total Teams': total_teams,
                        'CTF Points': ctf_points_value,
                        'Rating Points': rating_points_value,
                        'Rank Percentile': rank_percentile,
                        'Event URL': event_url if event_url else 'N/A'
                    })
                    print(f"  Added: {event_name} (Year: {year_str}, Rank: {place}, Rating Pts: {rating_points_value})")
                except Exception as e:
                    print(f"Error parsing row {row_idx+1} for year {year_str}: {row.text.strip()} - {e}")
            else:
                print(f"Skipping row with unexpected number of columns ({len(cols)}): {row.text.strip()}")
    
    if not participated_ctfs:
        print("No CTFs found after scraping.")
        return []

    df = pd.DataFrame(participated_ctfs)
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce').fillna(0).astype(int)
    df = df.iloc[::-1]
    df = df.sort_values(by='Year', ascending=True, kind='mergesort')

    print(f"Total CTFs scraped and processed: {len(df)}")
    return df.to_dict('records')

# --- Google Apps Script Interaction ---
def send_data_to_apps_script(data, web_app_url, secret_token):
    # Note: The placeholder checks are removed here as we expect env vars to be set or script to exit.
    # The main execution block will handle the check for missing env vars.
    
    print(f"Sending data to Google Apps Script Web App...")
    try:
        url_with_token = f"{web_app_url}?token={secret_token}"
        headers = {'Content-Type': 'application/json'}
        response = requests.post(url_with_token, json=data, headers=headers, timeout=45)
        response.raise_for_status() 
        
        response_json = response.json()
        if response_json.get("status") == "success":
            print(f"Apps Script Response: {response_json.get('message')}")
            return True
        else:
            print(f"Error from Apps Script: {response_json.get('message')}")
            return False
    except requests.exceptions.Timeout:
        print("Failed to send data to Apps Script: Request timed out.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Failed to send data to Apps Script: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        return False
    except ValueError: # Includes JSONDecodeError
        print(f"Could not decode JSON response from Apps Script.")
        if 'response' in locals() and response: # check if response variable exists
            print(f"Response content: {response.text}")
        return False

# --- Chart Generation ---
def generate_progress_chart(data, filename="progress_chart.png"):
    plt.style.use('dark_background')

    if not data:
        print("No data to generate chart.")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, 'No CTF Data Available to Plot',
                horizontalalignment='center', verticalalignment='center',
                fontsize=12, color='lightgray')
        ax.set_xticks([])
        ax.set_yticks([])
        fig.patch.set_facecolor('#1e1e1e')
        ax.set_facecolor('#1e1e1e')
        plt.savefig(filename, bbox_inches='tight', facecolor=fig.get_facecolor())
        print(f"Empty/Placeholder chart saved as {filename}")
        return

    df = pd.DataFrame(data)
    
    df['Rank Percentile'] = pd.to_numeric(df['Rank Percentile'], errors='coerce')
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce').fillna(0).astype(int)
    df['Event Label'] = df['Year'].astype(str) + ": " + df['Event Name'].str.slice(0, 25)

    if df.empty or df['Rank Percentile'].isnull().all():
        print("No valid rank percentiles to plot after processing.")
        generate_progress_chart([], filename)
        return

    fig, ax1 = plt.subplots(figsize=(18, 9))
    fig.patch.set_facecolor('#1e1e1e')
    ax1.set_facecolor('#282828')

    percentile_color = 'cyan'
    ax1.set_xlabel('CTF Event (Chronological Order)', fontsize=12, labelpad=15, color='lightgray')
    ax1.set_ylabel('Rank Percentile (Lower is better)', color=percentile_color, fontsize=12)
    
    valid_percentile_df = df.dropna(subset=['Rank Percentile'])
    if not valid_percentile_df.empty:
        ax1.plot(valid_percentile_df['Event Label'], valid_percentile_df['Rank Percentile'], 
                 color=percentile_color, marker='^', linestyle='-', linewidth=2, markersize=7, 
                 label='Rank Percentile')
        
        for i, row in valid_percentile_df.iterrows():
            ax1.annotate(f"{row['Rank Percentile']:.1f}%", 
                         (row['Event Label'], row['Rank Percentile']),
                         textcoords="offset points", xytext=(0, 10),
                         ha='center', fontsize=9, color=percentile_color,
                         bbox=dict(boxstyle="round,pad=0.3", fc="#333333", ec="none", alpha=0.7))

    ax1.tick_params(axis='y', labelcolor=percentile_color, labelsize=10, color='gray')
    ax1.tick_params(axis='x', rotation=65, labelsize=9, color='gray')
    for label in ax1.get_xticklabels():
        label.set_horizontalalignment('right')
        label.set_color('lightgray')

    ax1.grid(True, axis='y', linestyle=':', alpha=0.4, color='gray')
    ax1.grid(False, axis='x')

    if not valid_percentile_df.empty:
        ax1.invert_yaxis()
        min_val = valid_percentile_df['Rank Percentile'].min()
        max_val = valid_percentile_df['Rank Percentile'].max()
        padding = (max_val - min_val) * 0.1
        if max_val == min_val or padding == 0: padding = 5 
        ax1.set_ylim(max_val + padding, min_val - padding)

    fig.suptitle(f'{TEAM_NAME} - CTF Rank Percentile Over Time', fontsize=16, fontweight='bold', color='white')
    if not valid_percentile_df.empty:
        ax1.legend(loc='upper right', fontsize=10, framealpha=0.5)

    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    
    plt.savefig(filename, bbox_inches='tight', facecolor=fig.get_facecolor(), dpi=100)
    print(f"Chart saved as {filename}")

# --- Main Execution ---
if __name__ == "__main__":
    print("--- CTF Progress Tracker Started ---")
    ctf_data = scrape_team_ctf_data()

    if ctf_data:
        print(f"\n--- Data Scraped ({len(ctf_data)} events) ---")
        
        apps_script_url = os.getenv('APPS_SCRIPT_WEB_APP_URL')
        apps_script_token = os.getenv('APPS_SCRIPT_SECRET_TOKEN')

        if not apps_script_url or not apps_script_token:
            print("\nERROR: APPS_SCRIPT_WEB_APP_URL and/or APPS_SCRIPT_SECRET_TOKEN environment variables are not set.")
            print("Please set them for the script to connect to Google Apps Script.")
            print("Skipping Google Sheet update.")
            sheet_updated_successfully = False # Explicitly set to false
        else:
            print("\n--- Attempting to Update Google Sheet via Apps Script ---")
            sheet_updated_successfully = send_data_to_apps_script(ctf_data, apps_script_url, apps_script_token)
        
        if sheet_updated_successfully: # This check is now after the potential skip
            print("Google Sheet update attempt finished successfully.")
        # No 'else' here because the error/skip message is handled above

        print("\n--- Generating Progress Chart ---")
        generate_progress_chart(ctf_data) # Generate chart even if sheet update failed/skipped
        
    else:
        print("\nNo CTF data scraped. Generating an empty chart if it doesn't exist.")
        if not os.path.exists("progress_chart.png"):
            generate_progress_chart([])

    print("\n--- CTF Progress Tracker Finished ---")
