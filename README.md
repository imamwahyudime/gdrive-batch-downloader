# Google Drive Batch Downloader

Downloads files and folders from a Google Drive shared link.

## Description:

This script downloads all files and subfolders from a Google Drive shared folder to your local computer.  It supports both service account authentication (recommended for automation) and interactive user authentication.  
It can be used via a graphical user interface (GUI) or from the command line.

**In short, this code can:**

* Act like an automatic downloader robot from shared links. Which is great other than you manually download each files or waiting google drive to zip all the files and split them into parts then have the chance for the downloaded part to be failed/corrupt.
* Keep all the folders and files organized on your computer exactly as they were in the shared Drive.
* Use a special "program account" to download things, which is great for automated tasks or when you're not personally logged in all the time.

## Features:

* **Downloads from shared links:** Downloads all files and folders from a Google Drive shared folder.
* **Recursive download:** Handles subfolders and downloads their contents as well, preserving the folder structure.
* **Service account support:** Supports using a service account for authentication, which is ideal for automated downloads and avoids the need for manual login.
* **Interactive authentication:** Also supports interactive authentication (less preferred for automation) where you log in through your browser.
* **GUI and command-line interface:** Provides both a graphical user interface (GUI) and a command-line interface (CLI).
* **Error handling:** Includes robust error handling and logging.
* **File Overwriting:** Handles existing files by overwriting them.
* **Logging:** Logs download progress and any errors.

## Requirements:

* Python 3.6 or later
* `google-api-python-client`
* `google-auth-httplib2`
* `google-auth`
* `tkinter` (if you want to use the GUI)

You can install the required packages using pip:

```bash
pip install google-api-python-client google-auth-httplib2 google-auth
```

## Setup:

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd google-drive-downloader
    ```

2.  **(Optional) Set up a service account (Recommended):**

    * Go to the [Google Cloud Console](https://console.cloud.google.com/).
    * Create a new project or select an existing one.
    * Enable the "Google Drive API".
    * Create a service account.
    * Download the service account JSON file (e.g., `service_account.json`) and place it in the same directory as the script.

## Usage:

### GUI

1.  Run the script: `python script.py`
2.  Enter the Google Drive shared link in the "Shared Drive Link" field.
3.  Enter the download path or click "Browse" to select a directory.
4.  Check "Use Service Account" if you have set up a service account (recommended). Uncheck it to use interactive authentication.
5.  Click "Download".

### Command Line

python script.py <shared_url> <download_path> [--no-service-account]
* `<shared_url>`: The Google Drive shared URL.
* `<download_path>`: The path to download the files to.
* `[--no-service-account]`: Optional flag. If present, the script will \*not\* use a service account and will attempt interactive authentication (not recommended for automated scripts). If absent, the script \*will\* attempt to use a service account.

## Important Notes:

* **Service Account:** Using a service account is the recommended way to use this script, especially for automated downloads. It avoids the need to manually authenticate each time. Make sure the service account has the necessary permissions to access the shared folder.
* **Permissions:** The script requires read-only access to the Google Drive folder.
* **Error Handling:** The script includes error handling, but you should still check the output for any errors.
* **Rate Limits:** Be mindful of Google Drive API rate limits. Downloading very large amounts of data may be subject to these limits.

## Disclaimer:

This script is provided as-is, with no guarantees. Use it at your own risk. The author is not responsible for any data loss or other issues that may arise from the use of this script.
