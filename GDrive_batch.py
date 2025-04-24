import io
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_httplib2 import AuthorizedHttp
from google.oauth2 import credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseDownload
import logging
import json

# Constants
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
# Change this to the name you want for the downloaded folder
BASE_DOWNLOAD_FOLDER = "Downloaded_Files"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_service_account_credentials(filename='service_account.json'):
    """Gets credentials using a service account."""
    try:
        if not os.path.exists(filename):
            raise FileNotFoundError(f"File not found: {filename}.  Download your service account JSON from the Google Cloud Console.")
        creds = service_account.Credentials.from_service_account_file(
            filename, scopes=SCOPES)
        return creds
    except Exception as e:
        logging.error(f"Error getting service account credentials: {e}")
        return None

def get_credentials_interactive(token_path='token.json'):
    """Gets user credentials via the installed application flow.  Less preferred."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_path):
        try:
            creds = credentials.Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception as e:
            logging.error(f"Error loading credentials from {token_path}: {e}")
            creds = None # Force refresh
    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.error(f"Error refreshing credentials: {e}")
                return None
        else:
            logging.error("Credentials need to be obtained interactively.  This is not recommended for background processes.")
            return None # Cannot obtain without user interaction
        # Save the credentials for the next run
        try:
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            logging.warning(f"Failed to save credentials to {token_path}: {e}")
            # Non-critical error, continue.
    return creds

def get_credentials(use_service_account=True, service_account_file='service_account.json', token_path='token.json'):
    """
    Gets Google API credentials.  Prefers service account, falls back to interactive.

    Args:
        use_service_account (bool): Whether to use a service account.
        service_account_file (str): Path to the service account JSON file.
        token_path (str): Path to save the user's token.json (for interactive auth).

    Returns:
        google.oauth2.credentials.Credentials or None: The credentials, or None on failure.
    """
    if use_service_account:
        creds = get_service_account_credentials(service_account_file)
        if creds:
            logging.info("Successfully loaded service account credentials.")
            return creds
        else:
            logging.warning("Failed to load service account credentials.  Falling back to user authentication.")
    # Fallback to user authentication (if service account fails or not requested)
    return get_credentials_interactive(token_path)


def create_service(credentials):
    """
    Creates the Google Drive API service.

    Args:
        credentials: The credentials to use.

    Returns:
        googleapiclient.discovery.Resource: The Drive API service, or None on error.
    """
    try:
        service = build('drive', 'v3', credentials=credentials)
        logging.info("Successfully created Google Drive API service.")
        return service
    except Exception as e:
        logging.error(f"Error creating Google Drive service: {e}")
        return None

def get_shared_folder_id(shared_url):
    """
    Extracts the folder ID from a Google Drive shared URL.

    Args:
        shared_url (str): The shared URL.

    Returns:
        str: The folder ID, or None if the URL is invalid.
    """
    if not shared_url:
        return None
    try:
        # URL format: https://drive.google.com/drive/folders/{folder_id}?usp=sharing
        # URL format: https://drive.google.com/folderview?id={folder_id}&usp=sharing  (older format)
        if "folders/" in shared_url:
            folder_id = shared_url.split("folders/")[1].split("?")[0]
        elif "folderview?id=" in shared_url:
            folder_id = shared_url.split("folderview?id=")[1].split("&")[0]
        else:
            return None
        return folder_id
    except IndexError:
        return None
    except TypeError:
        return None

def list_files_in_folder(service, folder_id):
    """
    Lists all files and subfolders within a specified folder.  Includes recursive listing.

    Args:
        service: The Google Drive API service.
        folder_id: The ID of the folder to list.

    Returns:
        list: A list of dictionaries, where each dictionary represents a file or folder.
              Returns an empty list on error.  Handles pagination.
    """
    results = []
    try:
        page_token = None
        while True:
            # Add 'supportsAllDrives': True to include files in shared drives.
            results_page = service.files().list(q=f"'{folder_id}' in parents and trashed=false",
                                             fields="nextPageToken, files(id, name, mimeType)",
                                             pageToken=page_token,
                                             supportsAllDrives=True,
                                             includeItemsFromAllDrives=True).execute()
            if not results_page:
                break
            items = results_page.get('files', [])
            if not items:
                break
            results.extend(items)
            page_token = results_page.get('nextPageToken')
            if not page_token:
                break
        return results
    except HttpError as error:
        logging.error(f"An error occurred: {error}")
        return []  # Return empty list on error to avoid crashing

def download_file(service, file_id, file_name, download_path):
    """
    Downloads a file from Google Drive.

    Args:
        service: The Google Drive API service.
        file_id: The ID of the file to download.
        file_name: The name of the file.
        download_path: The path to download the file to.
    """
    try:
        # Get the file metadata to check if it's a folder.
        file_metadata = service.files().get(fileId=file_id, supportsAllDrives=True).execute()
        if file_metadata['mimeType'] == 'application/vnd.google-apps.folder':
            logging.info(f"Skipping download of folder: {file_name} (ID: {file_id})")
            return  # Skip folders, we handle them in list_files_in_folder

        # Check if the file already exists and handle overwriting
        file_path = os.path.join(download_path, file_name)
        if os.path.exists(file_path):
            logging.warning(f"File already exists: {file_path}. Overwriting.")

        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.FileIO(file_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            # No progress bar in GUI version.
            # print(f"Download {int(status.progress() * 100)}.")
        logging.info(f"Downloaded: {file_name} to {file_path}")
    except HttpError as error:
        logging.error(f"An error occurred during download of {file_name}: {error}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during download of {file_name}: {e}")

def process_files(service, files, download_path, parent_folder_name=""):
    """Processes the list of files, downloading them or recursively entering folders.

       Handles subfolders correctly by creating corresponding directories.

    Args:
        service: The Google Drive API service.
        files (list):  A list of file dictionaries.
        download_path (str): The base download path.
        parent_folder_name (str): The name of the parent folder (for creating subdirectories).
    """
    for file_data in files:
        file_id = file_data['id']
        file_name = file_data['name']
        mime_type = file_data['mimeType']

        # Construct the correct download path, including subfolders
        current_download_path = download_path
        if parent_folder_name:
            current_download_path = os.path.join(download_path, parent_folder_name)
            # Create the subfolder if it doesn't exist
            if not os.path.exists(current_download_path):
                try:
                    os.makedirs(current_download_path)
                    logging.info(f"Created directory: {current_download_path}")
                except OSError as e:
                    logging.error(f"Failed to create directory {current_download_path}: {e}")
                    # Don't try to download into a folder we couldn't create.  Log and continue.
                    continue

        if mime_type == 'application/vnd.google-apps.folder':
            logging.info(f"Processing folder: {file_name} (ID: {file_id})")
            # Recursively process files in the subfolder
            sub_files = list_files_in_folder(service, file_id)
            if sub_files:
                process_files(service, sub_files, download_path, os.path.join(parent_folder_name, file_name) if parent_folder_name else file_name)
            else:
                logging.info(f"Folder {file_name} is empty.")

        else:
            download_file(service, file_id, file_name, current_download_path)

def download_files_from_shared_link(shared_url, download_path, use_service_account=True, service_account_file='service_account.json', token_path='token.json'):
    """
    Downloads all files and subfolders from a Google Drive shared link.

    Args:
        shared_url (str): The Google Drive shared URL.
        download_path (str): The path to download the files to.
        use_service_account (bool): Whether to use a service account.
        service_account_file (str): Path to the service account JSON file.
        token_path (str): Path to the user's token.json file.
    """
    if not shared_url:
        logging.error("Shared URL is required.")
        return False  # Indicate failure

    if not download_path:
        logging.error("Download path is required.")
        return False # Indicate failure

    folder_id = get_shared_folder_id(shared_url)
    if not folder_id:
        logging.error("Invalid Google Drive shared URL.")
        return False # Indicate failure

    credentials = get_credentials(use_service_account, service_account_file, token_path)
    if not credentials:
        logging.error("Failed to obtain credentials.")
        return False # Indicate failure

    service = create_service(credentials)
    if not service:
        logging.error("Failed to create Google Drive service.")
        return False # Indicate failure

    files = list_files_in_folder(service, folder_id)
    if not files:
        logging.warning("No files found in the shared folder or error accessing folder.")
        return True #  No files is not an error, but an empty folder.

    process_files(service, files, download_path)
    return True # Indicate success

class DriveDownloaderGUI(tk.Tk):
    """
    Graphical User Interface for the Google Drive Downloader.
    """
    def __init__(self):
        super().__init__()

        self.title("Google Drive Downloader")
        self.geometry("600x400")  # Increased size for better layout
        self.configure(bg="#f0f0f0")  # Light gray background

        # Style for the widgets
        self.style = ttk.Style(self)
        self.style.theme_use("clam")  # Use a modern theme
        self.style.configure("TLabel", background="#f0f0f0", foreground="#333", font=("Arial", 12))
        self.style.configure("TButton", padding=10, font=("Arial", 12), relief="raised")
        self.style.configure("TEntry", padding=5, font=("Arial", 12))
        self.style.configure("TCheckbutton", background="#f0f0f0", foreground="#333", font=("Arial", 12))
        self.style.configure("TFrame", background="#f0f0f0")  #Set frame background.

        # Main frame
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(padx=20, pady=20, fill="both", expand=True)

        # Variables
        self.shared_link = tk.StringVar()
        self.download_path = tk.StringVar()
        self.use_service_account = tk.BooleanVar(value=True)  # Default to service account
        self.status_text = tk.StringVar(value="Ready")  # Status message

        # UI elements
        self.create_widgets()

    def create_widgets(self):
        """Creates the UI elements."""

        # Shared Link Input
        ttk.Label(self.main_frame, text="Shared Drive Link:").pack(pady=(0, 5), anchor="w")
        link_entry = ttk.Entry(self.main_frame, textvariable=self.shared_link, width=50)
        link_entry.pack(pady=(0, 10), fill="x")

        # Download Path Selection
        ttk.Label(self.main_frame, text="Download Path:").pack(pady=(0, 5), anchor="w")
        path_frame = ttk.Frame(self.main_frame)  # Use a frame for better layout
        path_frame.pack(pady=(0, 10), fill="x")
        path_entry = ttk.Entry(path_frame, textvariable=self.download_path, width=40)
        path_entry.pack(side="left", fill="x", expand=True)
        browse_button = ttk.Button(path_frame, text="Browse", command=self.browse_directory)
        browse_button.pack(side="left", padx=(5, 0))

        # Use Service Account Checkbox
        self.service_account_check = ttk.Checkbutton(
            self.main_frame,
            text="Use Service Account (Recommended)",
            variable=self.use_service_account
        )
        self.service_account_check.pack(pady=(0, 15), anchor="w")

        # Download Button
        download_button = ttk.Button(self.main_frame, text="Download", command=self.start_download)
        download_button.pack(pady=(10, 20), fill="x")

        # Status Label
        ttk.Label(self.main_frame, text="Status:").pack(pady=(0, 5), anchor="w")
        status_label = ttk.Label(self.main_frame, textvariable=self.status_text, foreground="blue", font=("Arial", 12, "italic"))
        status_label.pack(pady=(0, 0), anchor="w")

        # Error Label (initially hidden)
        self.error_label = ttk.Label(self.main_frame, text="", foreground="red", font=("Arial", 12))
        self.error_label.pack(pady=(10, 0), anchor="w")
        self.error_label.pack_forget()  # Hide initially

    def browse_directory(self):
        """Opens a directory dialog and sets the download path."""
        download_folder = filedialog.askdirectory(initialdir=os.getcwd())
        if download_folder:
            self.download_path.set(download_folder)

    def start_download(self):
        """Starts the download process in a separate thread."""
        shared_url = self.shared_link.get()
        download_path = self.download_path.get()
        use_service_account = self.use_service_account.get()

        if not shared_url:
            self.show_error("Please enter a shared Drive link.")
            return
        if not download_path:
            self.show_error("Please select a download path.")
            return

        # Clear any previous error message
        self.error_label.pack_forget()

        # Disable the download button to prevent multiple downloads
        for child in self.main_frame.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == "Download":
                child.config(state="disabled")
                break

        self.status_text.set("Downloading...")
        # Create a thread to perform the download
        threading.Thread(target=self.perform_download, args=(shared_url, download_path, use_service_account)).start()

    def perform_download(self, shared_url, download_path, use_service_account):
        """
        Performs the download operation.  This runs in a separate thread.

        Args:
            shared_url (str): The shared URL.
            download_path (str): The download path.
            use_service_account (bool): Whether to use a service account.
        """
        # Ensure the download path exists
        if not os.path.exists(download_path):
            try:
                os.makedirs(download_path)
            except OSError as e:
                logging.error(f"Error creating download directory: {e}")
                self.update_status("Error: Could not create download directory.")
                self.enable_download_button()
                return

        success = download_files_from_shared_link(shared_url, download_path, use_service_account)
        if success:
            self.update_status("Download complete!")
        else:
            self.update_status("Download failed.") # download_files_from_shared_link already logs the specific error.
        self.enable_download_button()

    def update_status(self, text):
        """Updates the status text in the GUI.  Must be called from the main thread."""
        self.after(0, self.status_text.set, text)

    def enable_download_button(self):
        """Enables the download button.  Must be called from the main thread."""
        self.after(0, self.enable_download_button_internal)

    def enable_download_button_internal(self):
        """Internal function to enable the download button."""
        for child in self.main_frame.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") == "Download":
                child.config(state="normal")
                break

    def show_error(self, message):
        """Displays an error message in the GUI."""
        self.error_label.config(text=message)
        self.error_label.pack(pady=(10, 0), anchor="w")  # Make sure it's visible
        # Optionally, clear the error message after a few seconds
        self.after(5000, self.clear_error)

    def clear_error(self):
        """Clears the error message."""
        self.error_label.pack_forget()

if __name__ == "__main__":
    # Check for command-line arguments.  If provided, run in non-GUI mode.
    if len(sys.argv) > 1:
        if len(sys.argv) < 3:
            print("Usage: python script.py <shared_url> <download_path> [--no-service-account]")
            sys.exit(1)
        shared_url = sys.argv[1]
        download_path = sys.argv[2]
        use_service_account = "--no-service-account" not in sys.argv
        print(f"Downloading from {shared_url} to {download_path} using service account: {use_service_account}")
        success = download_files_from_shared_link(shared_url, download_path, use_service_account)
        if success:
            print("Download completed successfully.")
        else:
            print("Download failed.")
        sys.exit(0)  # Exit after non-GUI execution

    # Otherwise, run the GUI.
    app = DriveDownloaderGUI()
    app.mainloop()
