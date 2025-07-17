# Bing Image Downloader

This application allows you to search for and download images from Bing. It provides a graphical user interface (GUI) for an interactive experience, as well as a command-line interface (CLI) for scripting and automation.

## Features

- **Graphical User Interface (GUI):** A user-friendly interface for searching, viewing, and downloading images.
- **Advanced Filtering:** Filter images by source, title, size, date, and how long ago they were posted.
- **Image Selection:** Select multiple images to download at once.
- **Image Details:** View detailed information about each image, including the source, size, and date.
- **Command-Line Interface (CLI):** A simple CLI for searching and downloading images from the command line.

## How to Run

### GUI

To run the GUI, execute the following command from the root of the project:

```bash
python3 -m bing_image_downloader.gui
```

### CLI

To use the CLI, you can run the `cli.py` script with a search query:

```bash
python3 -m bing_image_downloader.cli "Your search query"
```
