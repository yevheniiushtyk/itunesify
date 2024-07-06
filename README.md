# iTunesify

![iTunesify Logo](/images/itunesify-logo.png)

**iTunesify** is a cross-platform Python script that utilizes the **iTunes API** to retrieve music release information, enabling you to **organize and tag your music library effectively.** Regardless of the type of music release—be it albums, singles, EPs, or others—iTunesify ensures your music library stays organized by generating a directory structure that groups your music files by artist and release type. It supports both **FLAC** and **MP3** files. The script automatically loops through each directory in the specified music directory, processing and organizing each album one by one, and continues until the last album has been organized. The user has control over each iTunes collection being organized and can choose a different collection from the iTunes API by making a custom search, as well as skip the collection and proceed to the next one. Compatible with Windows, macOS, and Linux, iTunesify offers a user-friendly way to manage your music collection effectively.

![iTunesify Screenshot](/images/screenshot.png)

## 📖 Table of Contents

1. **[🚀 Features](#-features)**
2. **[🎨 Cover Art](#-cover-art)**
3. **[🛠️ Setup and Installation](#️-setup-and-installation)**
   - **[Option 1: Using the Executable](#option-1-using-the-executable)**
   - **[Option 2: Working from Source](#option-2-working-from-source)**
   - **[Create and Activate a Virtual Environment](#create-and-activate-a-virtual-environment)**
   - **[Install Python Dependencies](#install-python-dependencies)**
   - **[Install System Dependencies](#install-system-dependencies)**
4. **[📚 Usage](#-usage)**
5. **[🚩 Command Line Flags (Args)](#-command-line-flags-args)**
6. **[⚙️ Configuration](#️-configuration)**
7. **[🔧 Troubleshooting](#-troubleshooting)**
8. **[🤝 Contributing](#-contributing)**
9. **[📜 License](#-license)**
10. **[🌟 Acknowledgments](#-acknowledgments)**

## 🚀 Features

- **Automatically loop through each album directory** within your specified music directory, processing and organizing each album one by one until the last album has been organized.
- **User control over the organization process:** Choose a different collection from the iTunes API by making a custom search or skip the current collection and proceed to the next one.
- **Search, fetch, and tag** your music files with metadata from the iTunes API, supporting both **FLAC** and **MP3** formats.
- Create **subdirectories for each release type** found on the iTunes API (e.g., **"Albums"** and **"Singles & EPs"**).
- **Clean up inconsistencies and unnecessary metadata** from FLAC files using **metaflac**.
- Re-encode FLAC files with **compression level 5** for optimal balance between file size and compression.
- Add an **Audio MD5 checksum** to ensure file integrity.
- **Save the highest resolution uncompressed cover art** when possible, and use the standard resolution as a fallback when not available.

## 🎨 Cover Art

iTunesify fetches the **cover art for each release** using the iTunes API. By default, it attempts to retrieve the uncompressed high-resolution cover art. If the uncompressed high-resolution cover art is not available, it falls back to the standard resolution.

The cover art is stored in the same directory as the music files, with the filename following this format: "cover.{extension}". If a cover art file with the same name already exists in the directory, it will be replaced by the new cover art.

**Note:** When processing both **FLAC** and **MP3** files, **embedded cover art will be removed** during the metadata cleanup process. The new cover art fetched from the iTunes API will be saved separately in the same directory as the music files.

## 🛠️ Setup and Installation

### Option 1: Using the Executable

For a near hassle-free experience, use the precompiled executable from the release section. Note that you will still need to install `flac` and `metaflac` separately, as they are not bundled within the executable. Follow the instructions in the [Install System Dependencies](#install-system-dependencies) section to install `flac` and `metaflac`.

Once you have installed `flac` and `metaflac`, download the executable from the release section and run it.

---

### Option 2: Working from Source

If you prefer to work with the source code, follow these steps:

1. **Clone the repository:**

    ```bash
    git clone https://github.com/yevhen2ii/itunesify
    ```

2. **Navigate to the project folder:**

    ```bash
    cd itunesify
    ```

#### Create and Activate a Virtual Environment

Create a virtual environment to prevent conflicts with other packages on your system:

1. **Create a virtual environment:**

    ```bash
    python -m venv venv
    ```

2. **Activate the virtual environment:**

    - For Windows:

        ```bash
        venv\Scripts\activate
        ```

    - For macOS/Linux:

        ```bash
        source venv/bin/activate
        ```

#### Install Python Dependencies

With the virtual environment activated, use pip to install the required Python packages:

```bash
pip install -r requirements.txt
```

#### Install System Dependencies

iTunesify depends on two external tools: **flac** and **metaflac**. Ensure that both `flac` and `metaflac` are installed on your system, available in your `PATH`, or set their paths in the `config.json` file. For more information on setting the paths in `config.json`, refer to the [Configuration](#️-configuration) section.

To install `flac` and `metaflac`, use the following command:

- For macOS:

    ```bash
    brew install flac
    ```

- For Ubuntu:

    ```bash
    sudo apt install flac
    ```

**Note:** When installing flac, metaflac will also be installed by default on macOS and Ubuntu. For more information and alternative downloads, visit the official FLAC website: https://xiph.org/flac/download.html

## 📚 Usage

1. Organize your music library into a directory structure where each artist has their own sub-directory, and within that sub-directory, each music collection has its own sub-directory. The audio files should be stored within these sub-directories. For example:

```
music/
    artist1/
        album1/
            song1.flac
            song2.flac
        album2/
            song1.flac
            song2.flac
    artist2/
        album1/
            song1.flac
            song2.flac
        album2/
            song1.flac
            song2.flac
```

2. Download the iTunesify executable file or ensure you have the `itunesify.py` script from the cloned repository.
3. Open the command prompt or terminal and navigate to the directory containing the iTunesify executable file or the `itunesify.py` script.
4. Run the script by typing the following command:

For the executable:

```bash
itunesify -d [music_directory_path]
```

For the source code:
```bash
python itunesify.py -d [music_directory_path]
```

Replace `[music_directory_path]` with the full path of the music directory that you have created in the format shown above, enclosed in quotes.

The script will automatically walk through your music library directory structure, extracting artist and collection information from the audio files to make a search query to the iTunes API. You will be prompted to confirm the organization for each collection found on iTunes, and after confirmation, the script will organize your music files accordingly.


## 🚩 Command Line Flags (Args)

You can use command line flags (arguments) to customize the behavior of iTunesify when running the script or executable. The following flags are supported:

- **`-c, --config`**: Specify a custom configuration file (JSON) path. By default, the script or executable will look for the configuration file (`config.json`) in the same directory as the script or executable.
- **`-d, --directory`**: Specify the music directory path. This is the path to the directory containing your music library, which will be organized by the script.

## ⚙️ Configuration

The configuration file `config.json` contains the paths to various executables and files used by the script. Here is an example of what `config.json` might look like on Windows:

```json
{
    "music_directory": "C:/Users/{username}/Downloads/music",
    "censored_words_file": "censored_words.txt",
    "flac_path": "flac",
    "metaflac_path": "metaflac",
}
```

- **`"metaflac_path"`**: The path to the `metaflac` executable. This is used to clean up inconsistencies and unnecessary metadata from FLAC files.
- **`"flac_path"`**: The path to the `flac` executable. This is used to re-encode FLAC files with compression level 5 for optimal balance between file size and compression.

**Note:** If **metaflac** and **flac** are already in your system's `PATH`, you can leave these values unchanged.

- **`"censored_words_file"`**: The path to the `censored_words.txt` file, which contains a list of censored words that should be replaced with their uncensored counterparts in album and track names. The format of the file is `censored_word:uncensored_word`. Note that this list is case-sensitive, so you need a new entry for each different case formatting of the word.
- **`"music_directory"`**: The path to the directory containing your music library. This is the directory that will be organized by the script.

## 🔧 Troubleshooting

If you encounter any issues while using iTunesify, consider the following troubleshooting steps:

1. Double-check your music directory structure to ensure it matches the format expected by the script.
2. Verify that you have installed all required Python dependencies and system dependencies if you are working from source.
3. Ensure that your virtual environment is activated before running the script if you are working from source.
4. Make sure that the `flac` and `metaflac` binaries are in your system `PATH` or placed in the root directory of the script.
5. Consult the script's output for any error messages or warnings that may provide more information about the issue.

If you continue to experience problems, don't hesitate to open an issue on the GitHub repository. Please include as much information as possible, such as your operating system, any error messages, and the steps you took before encountering the issue.

## 🤝 Contributing

We welcome contributions to improve iTunesify and make it even more user-friendly. If you would like to contribute, please follow these steps:

1. Fork the repository on GitHub.
2. Clone your fork to your local machine.
3. Create a new branch for your feature or bugfix, using a descriptive name.
4. Make your changes and commit them to your branch.
5. Push your branch to your fork on GitHub.
6. Open a pull request from your branch to the original repository.

When submitting a pull request, please provide a clear description of your changes, including any issues they address, and any additional steps required to test or use your changes.

## 📜 License

iTunesify is licensed under the MIT License. See the **[LICENSE](LICENSE)** file for more information.

## 🌟 Acknowledgments

Special thanks to the developers of the following libraries and tools that have been used in this project:

- **[itunespy](https://github.com/sleepyfran/itunespy)**
- **[mutagen](https://github.com/quodlibet/mutagen)**
- **[rich](https://github.com/Textualize/rich)**
- **[requests](https://github.com/psf/requests)**
- **[Pillow](https://github.com/python-pillow/Pillow)**
- **[flac](https://xiph.org/flac/)**
- **[metaflac](https://xiph.org/flac/documentation_tools_metaflac.html)**
