import os
import re
import json
import itunespy
import requests
import argparse
import subprocess

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3

from urllib.parse import urlparse
from io import BytesIO
from PIL import Image

from rich.traceback import install
from rich.console import Console, ConsoleRenderable
from rich.table import Table
from rich import box
from rich.text import Text
from rich.style import Style
from rich.progress import Progress

class BoldPrompt(ConsoleRenderable):
    def __init__(self, color):
        self.color = color

    def __rich_console__(self, console, options):
        text = Text(" [y/n] ", style=Style(bold=True, color=self.color), end="")
        yield text

class Track:
    def __init__(self, path, audio_tags, audio_file_type):
        self.path = path
        self.audio_tags = audio_tags
        self.audio_file_type = audio_file_type

    def clear_tags(self):
        if self.audio_file_type == "mp3":
            self.audio_tags.delete()
        else:
            self.audio_tags.clear()
            self.audio_tags.clear_pictures()

    def get_tag(self, tag_name):
        return self.audio_tags.get(tag_name)

    def set_tag(self, tag_name, value):
        self.audio_tags[tag_name] = value

    def save_tags(self):
        self.audio_tags.save()

class iTunesify:
    def load_config(self, config_file):
        with open(config_file, "r") as f:
            config = json.load(f)
        return config

    def __init__(self, music_directory_arg=None, config_file=None):
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), "config.json")
        config = self.load_config(config_file)
        self.metaflac_path = config["metaflac_path"]
        self.flac_path = config["flac_path"]
        self.censored_words_file = config["censored_words_file"]
        self.music_directory = config["music_directory"]

        if music_directory_arg:
            self.music_directory = music_directory_arg
        elif not self.music_directory or self.music_directory == "/path/to/your/music/directory":
            self.music_directory = console.input("[b]Enter the path of a music directory you wish to iTunesify (you can drag and drop):[/b] ").rstrip().strip("\"").strip("'\"")

    def display_success_message(self, itunes_collection, audio_file_type):
        num_tracks = len(itunes_collection.get_tracks())
        files_str = "file" if num_tracks == 1 else "files"

        itunes_artist_name = itunes_collection.artist_name
        itunes_collection_name = itunes_collection.collection_censored_name
        itunes_release_date_year = itunes_collection.parsed_release_date.year

        console.print(f"\n[b][orchid]{num_tracks} {audio_file_type} {files_str} [green]successfully tagged[/green] with [gold1]iTunes metadata[/gold1] for [gold1]{itunes_artist_name}[/gold1] - [gold1]{self.replace_censored_text(itunes_collection_name)} ({itunes_release_date_year})[/gold1][/orchid][/b]")

    def move_files(self, local_tracks, censored_collection_name, release_year, collection_path, artist_path):
        invalid_chars = ["<", ">", ":", "\"", "/", "\\", "|", "?", "*"]
        valid_chars = ["(", ")", "-", "'", "-", "-", "-", "-", "-"]
        for i, char in enumerate(invalid_chars):
            censored_collection_name = censored_collection_name.replace(char, valid_chars[i])

        audio_file_type = self.get_file_type(local_tracks[0])
        if audio_file_type == "flac":
            first_flac_file = os.path.join(os.path.dirname(local_tracks[0]), [f for f in os.listdir(os.path.dirname(local_tracks[0])) if f.endswith(".flac")][0])

            sample_rate = subprocess.check_output(["metaflac", "--show-sample-rate", first_flac_file]).decode().strip()
            bitrate = subprocess.check_output(["metaflac", "--show-bps", first_flac_file]).decode().strip()

            bitrate_sample_rate = f"{bitrate}B-{int(sample_rate)/1000:.0f}kHz" if int(sample_rate) % 1000 == 0 else f"{bitrate}B-{int(sample_rate)/1000:.1f}kHz"

            new_collection_dir = f"{censored_collection_name} ({release_year}) [{audio_file_type.upper()}] [{bitrate_sample_rate}]"
        else:
            new_collection_dir = f"{censored_collection_name} ({release_year}) [{audio_file_type.upper()}]"

        if " - EP" in censored_collection_name or " - Single" in censored_collection_name:
            singles_eps_path = os.path.join(artist_path, "Singles & EPs")
            if not os.path.exists(singles_eps_path):
                os.mkdir(singles_eps_path)

            os.rename(collection_path, os.path.join(singles_eps_path, new_collection_dir))
        else:
            albums_path = os.path.join(artist_path, "Albums")
            if not os.path.exists(albums_path):
                os.mkdir(albums_path)

            os.rename(collection_path, os.path.join(albums_path, new_collection_dir))

    def save_itunes_cover(self, collection_path, itunes_collection):
        artwork_url = itunes_collection.get_artwork_url()
        uncompressed_url = artwork_url.replace(artwork_url.split("-")[0], "https://is5")
        uncompressed_url = uncompressed_url.replace("https://is5-ssl.mzstatic.com/image/thumb", "https://a5.mzstatic.com/us/r1000/0")
        last_slash_index = uncompressed_url.rindex("/")
        uncompressed_url = uncompressed_url[:last_slash_index]

        response = requests.get(uncompressed_url)
        if response.status_code != 200:
            response = requests.get(artwork_url)
            if response.status_code == 200:
                extension = os.path.splitext(urlparse(artwork_url).path)[1]
        else:
            extension = os.path.splitext(urlparse(uncompressed_url).path)[1]

        if response.status_code == 200:
            if extension.lower() == ".tif":
                img = Image.open(BytesIO(response.content))
                if img.mode == "RGB":
                    rgba_image = img.convert("RGBA")
                    rgba_image.save(os.path.join(collection_path, "cover.png"), "png")
                else:
                    img.save(os.path.join(collection_path, "cover.png"), "png")
                extension = ".png"
            elif extension.lower() == ".jpeg":
                extension = ".jpg"

            for root, dirs, files in os.walk(collection_path):
                for file in files:
                    if file.endswith((".jpg", ".jpeg", ".png")):
                        os.remove(os.path.join(root, file))

            has_music_files = any(file.endswith((".mp3", ".flac")) for file in os.listdir(collection_path))
            has_disc_dirs = any(d.startswith("Disc ") for d in os.listdir(collection_path))

            if not has_music_files and has_disc_dirs:
                for subdir in os.listdir(collection_path):
                    subdir_path = os.path.join(collection_path, subdir)
                    if os.path.isdir(subdir_path) and subdir.startswith("Disc "):
                        cover_path = os.path.join(subdir_path, "cover" + extension)
                        with open(cover_path, "wb") as f:
                            f.write(response.content)
            else:
                cover_path = os.path.join(collection_path, "cover" + extension)
                with open(cover_path, "wb") as f:
                    f.write(response.content)

                for subdir in os.listdir(collection_path):
                    subdir_path = os.path.join(collection_path, subdir)
                    if os.path.isdir(subdir_path) and subdir.startswith("Disc "):
                        sub_cover_path = os.path.join(subdir_path, "cover" + extension)
                        with open(sub_cover_path, "wb") as f:
                            f.write(response.content)


    def write_tags(self, local_track, itunes_track, itunes_collection, local_disc_count, local_disc_number, local_copyright):
        local_track.set_tag("artist", itunes_track.artist_name)
        local_track.set_tag("album", self.replace_censored_text(itunes_collection.collection_censored_name))
        local_track.set_tag("title", self.replace_censored_text(itunes_track.track_censored_name))
        local_track.set_tag("tracknumber", str(itunes_track.track_number).zfill(2))
        local_track.set_tag("date", str(itunes_collection.parsed_release_date.year))
        local_track.set_tag("genre", itunes_collection.primary_genre_name)
        local_track.set_tag("albumartist", itunes_collection.artist_name)

        if local_track.audio_file_type == "flac":
            local_track.set_tag("totaltracks", str(itunes_track.track_count).zfill(2))
            local_track.set_tag("discnumber", local_disc_number)
            local_track.set_tag("totaldiscs", local_disc_count)
        elif local_track.audio_file_type == "mp3":
            local_track.set_tag("tracknumber", f"{str(itunes_track.track_number).zfill(2)}/{str(itunes_collection.track_count).zfill(2)}")
            local_track.set_tag("discnumber", f"{local_disc_number}/{local_disc_count}")

        if local_track.get_tag("copyright"):
            local_track.set_tag("copyright", local_track.get_tag("copyright"))
        else:
            local_track.set_tag("copyright", itunes_collection.copyright)

        if local_copyright is not None and local_copyright != "":
            local_track.set_tag("copyright", local_copyright)
        else:
            local_track.set_tag("copyright", itunes_collection.copyright)

    def extract_disc_info(self, local_audio_file):
        collection_dir = os.path.dirname(local_audio_file)
        parent_dir = os.path.dirname(collection_dir)

        current_disc_dir = os.path.basename(collection_dir).lower()

        disc_pattern = re.compile(r"(?i)^(?:disc|cd)\s*\d+$")
        disc_dirs = [d for d in os.listdir(parent_dir) if disc_pattern.match(d)]

        if disc_pattern.match(current_disc_dir):
            disc_number = re.search(r"\d+", current_disc_dir).group().zfill(2)
            disc_count = str(len(disc_dirs)).zfill(2)
        else:
            disc_number = "01"
            disc_count = "01"
        return disc_count, disc_number

    def get_file_type(self, file_path):
        if file_path.endswith(".flac"):
            return "flac"
        elif file_path.endswith(".mp3"):
            return "mp3"

    def retag_files(self, local_tracks, itunes_collection):
        local_tracks_sorted = sorted(local_tracks, key=lambda x: int(self.get_audio_tags(x)["tracknumber"][0]))
        console.print(end="")
        with Progress() as progress:
            task = progress.add_task("Retagging files", total=len(local_tracks_sorted))

            for i, local_audio_file in enumerate(local_tracks_sorted):
                itunes_track = itunes_collection.get_tracks()[i]

                track_tags = self.get_audio_tags(local_audio_file)
                local_track = Track(local_audio_file, track_tags, self.get_file_type(local_audio_file))

                local_copyright = local_track.get_tag("copyright")

                if local_track.audio_file_type == "flac":
                    os.system(f"{self.metaflac_path} --remove-all \"{local_audio_file}\"")

                local_track.clear_tags()

                local_disc_count, local_disc_number = self.extract_disc_info(local_audio_file)
                self.write_tags(local_track, itunes_track, itunes_collection, local_disc_count, local_disc_number, local_copyright)

                local_track.save_tags()

                if local_track.audio_file_type == "flac":
                    os.system(f"{self.flac_path} -s -f \"{local_audio_file}\" -o \"{local_audio_file}\"")

                extension = os.path.splitext(local_audio_file)[1]
                new_file_name = f"{str(itunes_track.track_number).zfill(2)} {self.replace_censored_text(itunes_track.track_censored_name)}{extension}"

                invalid_chars = ["<", ">", ":", "\"", "/", "\\", "|", "?", "*"]
                valid_chars = ["(", ")", "-", "'", "-", "-", "-", "-", "-"]
                for i, char in enumerate(invalid_chars):
                    new_file_name = new_file_name.replace(char, valid_chars[i])

                new_audio_file = os.path.join(os.path.dirname(local_audio_file), new_file_name)
                os.rename(local_audio_file, new_audio_file)

                progress.update(task, advance=1)

    def handle_custom_search_input(self, search_input):
        while True:
            try:
                itunes_collections = itunespy.search_album(search_input)
                return itunes_collections
            except LookupError:
                console.print("[b][red]No collections found.[/red] [gold1]Please enter a valid search input.[/gold1][/b]")
                search_input = self.custom_search_or_skip("\n[b][gold1]Enter a new search input or [orchid]'s'[/orchid] to skip:[/gold1][/b] ")
                if not search_input:
                    return None

    def custom_search_or_skip(self, prompt_text):
        search_input = console.input(prompt_text)
        if search_input.lower() == "s":
            return None
        return search_input

    def print_search_results(self, itunes_collections):
        search_results_table = Table(show_header=True, box=box.ROUNDED, border_style="gold3")
        search_results_table.add_column("#", justify="right")
        search_results_table.add_column("Collection")
        search_results_table.add_column("Artist", justify="center")
        search_results_table.add_column("Year")
        search_results_table.add_column("Genre", justify="center")
        search_results_table.add_column("Tracks", justify="right")
        search_results_table.add_column("Explicitness", justify="center")

        console.print("\n[b][gold1]Search results:[/gold1][/b]\n")
        for idx, itunes_collection in enumerate(itunes_collections):
            itunes_artist_name = itunes_collection.artist_name
            itunes_collection_name = itunes_collection.collection_censored_name
            itunes_release_date_year = itunes_collection.parsed_release_date.year
            itunes_genre = itunes_collection.primary_genre_name
            itunes_track_count = len(itunes_collection.get_tracks())
            itunes_explicitness = itunes_collection.collection_explicitness

            explicitness_str = "[red]Explicit[/red]" if itunes_explicitness == "explicit" else "[green]Clean[/green]"

            search_results_table.add_row(
                f"{idx+1}",
                itunes_collection_name,
                itunes_artist_name,
                str(itunes_release_date_year),
                itunes_genre,
                str(itunes_track_count),
                explicitness_str,
            )

        console.print(search_results_table)

    def handle_collection_selection(self, itunes_collections, local_tracks):
        local_tracks_sorted = sorted(local_tracks, key=lambda x: int(self.get_audio_tags(x)["tracknumber"][0]))

        if not itunes_collections:
            self.print_local_tags(local_tracks_sorted)
            return None, False

        self.print_search_results(itunes_collections)
        num_results = len(itunes_collections)

        while True:
            selection = console.input("\n[b][gold1]Enter the number of the correct collection,[/gold1] [orchid]'c'[/orchid] [gold1]to perform a custom search, or[/gold1] [orchid]'s'[/orchid] [gold1]to skip:[/gold1][/b] ")
            if selection.lower() == "c":
                prompt_text = "[b][gold1]Enter a custom search input or [orchid]'s'[/orchid] to skip:[/gold1][/b] "
                search_input = self.custom_search_or_skip(prompt_text)
                if not search_input:
                    return None, False
                else:
                    itunes_collections = self.handle_custom_search_input(search_input)
                    if itunes_collections:
                        self.print_search_results(itunes_collections)
                        num_results = len(itunes_collections)
            elif selection.lower() == "s":
                return None, False
            elif selection.isdigit():
                selection_int = int(selection)
                if 1 <= selection_int <= num_results:
                    itunes_collection = itunes_collections[selection_int - 1]
                    self.print_local_tags(local_tracks_sorted)
                    self.print_itunes_tags(itunes_collection)
                    confirm_result = self.confirm_itunes_collection([itunes_collection], local_tracks_sorted)
                    if confirm_result[1]:
                        return confirm_result

    def print_itunes_tags(self, itunes_collection):
        itunes_artist_name = itunes_collection.artist_name
        itunes_collection_name = itunes_collection.collection_censored_name
        itunes_genre = itunes_collection.primary_genre_name
        itunes_release_date = itunes_collection.parsed_release_date.year
        itunes_track_count = len(itunes_collection.get_tracks())
        itunes_explicitness = itunes_collection.collection_explicitness
        explicitness_text = f"[red]Explicit[/red]" if itunes_explicitness == "explicit" else f"[green]Clean[/green]"

        tags_table = Table(show_header=True, box=box.ROUNDED, border_style="gold3")
        tags_table.add_column("Tag")
        tags_table.add_column("Value")
        tags_table.add_row("[b]Artist[/b]", f"[gold1]{itunes_artist_name}[/gold1]")
        tags_table.add_row("[b]Album[/b]", f"[gold1]{self.replace_censored_text(itunes_collection_name)}[/gold1]")
        tags_table.add_row("[b]Genre[/b]", f"[gold1]{itunes_genre}[/gold1]")
        tags_table.add_row("[b]Date[/b]", f"[gold1]{itunes_release_date}[/gold1]")
        tags_table.add_row("[b]Track count[/b]", f"[gold1]{str(itunes_track_count).zfill(2) if itunes_track_count != 0 else '0'}[/gold1]")

        console.print("\n[b][gold1]iTunes tags:[/gold1][/b]")
        console.print(tags_table)

        itunes_tracks_by_disc = {}
        for itunes_track in itunes_collection.get_tracks():
            disc_number = itunes_track.disc_number
            if disc_number not in itunes_tracks_by_disc:
                itunes_tracks_by_disc[disc_number] = []
            itunes_tracks_by_disc[disc_number].append(itunes_track)

        for disc_number, itunes_tracks in itunes_tracks_by_disc.items():
            tracks_table = Table(show_header=True, box=box.ROUNDED, border_style="gold3")
            tracks_table.add_column("#", justify="right")
            tracks_table.add_column("Track")

            for itunes_track in itunes_tracks:
                tracks_table.add_row(str(itunes_track.track_number).zfill(2), f"[gold1]{self.replace_censored_text(itunes_track.track_censored_name)}[/gold1]")

            if len(itunes_tracks_by_disc) > 1:
                console.print(f"\n[b][gold1]Disc {str(disc_number).zfill(2)} tracks:[/gold1][/b]")
            else:
                console.print(f"\n[b][gold1]iTunes tracks:[/gold1][/b]")
            console.print(tracks_table)

        console.print("\n[b][gold1]Explicitness:[/gold1][/b]", explicitness_text)

    def get_audio_tags(self, local_audio_file):
        if local_audio_file.endswith(".flac"):
            local_audio_tags = FLAC(local_audio_file)
        elif local_audio_file.endswith(".mp3"):
            local_audio_tags = EasyID3(local_audio_file)
        return local_audio_tags

    def print_local_tags(self, local_tracks):
        local_tracks_sorted = sorted(local_tracks, key=lambda x: int(self.get_audio_tags(x)["tracknumber"][0]))
        local_artist_name, local_collection_name, local_release_date, local_genre = self.get_local_tags(local_tracks_sorted)

        table = Table(show_header=True, box=box.ROUNDED, border_style="magenta")
        table.add_column("Tag")
        table.add_column("Value")

        table.add_row("[b]Artist[/b]", f"[orchid]{local_artist_name}[/orchid]")
        table.add_row("[b]Album[/b]", f"[orchid]{local_collection_name}[/orchid]")
        table.add_row("[b]Genre[/b]", f"[orchid]{local_genre}[/orchid]")
        table.add_row("[b]Date[/b]", f"[orchid]{local_release_date}[/orchid]")
        table.add_row("[b]Track count[/b]", f"[orchid]{str(len(local_tracks_sorted)).zfill(2) if len(local_tracks_sorted) != 0 else '0'}[/orchid]")

        console.print("\n[b][orchid]Local tags:[/orchid][/b]")
        console.print(table)

        local_tracks_by_disc = {}
        for local_audio_file in local_tracks_sorted:
            track_tags = self.get_audio_tags(local_audio_file)
            local_track = Track(local_audio_file, track_tags, self.get_file_type(local_audio_file))

            local_disc_number = int(track_tags.get("discnumber", [1])[0])
            if local_disc_number not in local_tracks_by_disc:
                local_tracks_by_disc[local_disc_number] = []
            local_tracks_by_disc[local_disc_number].append((local_track, track_tags))

        for disc_number in sorted(local_tracks_by_disc.keys()):
            local_tracks_data = local_tracks_by_disc[disc_number]
            sorted_tracks = sorted(local_tracks_data, key=lambda x: int(x[1]["tracknumber"][0]))

            tracks_table = Table(show_header=True, box=box.ROUNDED, border_style="magenta")
            tracks_table.add_column("#", justify="right")
            tracks_table.add_column("Track")

            for local_track_data in sorted_tracks:
                local_track, track_tags = local_track_data
                local_track_number = str(track_tags["tracknumber"][0]).zfill(2)
                local_track_name = track_tags["title"][0]

                tracks_table.add_row(local_track_number, f"[orchid]{local_track_name}[/orchid]")

            disc_number_str = str(disc_number).zfill(2)
            if len(local_tracks_by_disc) > 1:
                console.print(f"\n[b][orchid]Disc {disc_number_str} tracks:[/orchid][/b]")
            else:
                console.print("\n[b][orchid]Local tracks:[/orchid][/b]")
            console.print(tracks_table)



    def get_local_tags(self, local_tracks):
        local_artist_name = local_collection_name = local_release_date = local_genre = None
        for local_track in local_tracks:
            local_audio_tags = self.get_audio_tags(local_track)
            if not local_artist_name:
                local_artist_name = local_audio_tags["artist"][0]
            if not local_collection_name:
                local_collection_name = local_audio_tags["album"][0]
            if not local_release_date and "date" in local_audio_tags:
                local_release_date = local_audio_tags["date"][0]
            if not local_genre and "genre" in local_audio_tags:
                local_genre = local_audio_tags["genre"][0]
        return local_artist_name, local_collection_name, local_release_date, local_genre

    def levenshtein_distance(self, s1, s2):
        if len(s1) < len(s2):
            return self.levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def add_custom_tracks(self, itunes_collection, local_tracks):
        itunes_artist_name = itunes_collection.artist_name
        itunes_tracks = itunes_collection.get_tracks()

        local_track_count = len(local_tracks)

        updated_track_list = []

        for local_track in local_tracks:
            try:
                audio = FLAC(local_track)
            except MutagenError:
                continue

            if "title" in audio:
                local_track_name = audio["title"][0]
            else:
                local_track_full_name = os.path.splitext(os.path.basename(local_track))[0]
                local_track_name = local_track_full_name.split("(")[0].strip()
                local_track_name = re.sub(r"^\d+\s*\.?\s*", "", local_track_name)

            match_found = False
            for itunes_track in itunes_tracks:
                itunes_track_name = self.replace_censored_text(itunes_track.track_censored_name)
                itunes_track_name = itunes_track_name.split("(")[0].strip()

                distance = self.levenshtein_distance(local_track_name, itunes_track_name)
                if distance <= 2:
                    match_found = True
                    updated_track_list.append(itunes_track)

            if not match_found:
                if "tracknumber" in audio:
                    track_number = int(audio["tracknumber"][0])
                else:
                    track_number_match = re.search(r"\d+", os.path.basename(local_track))
                    if track_number_match:
                        track_number = int(track_number_match.group())
                    else:
                        continue

                custom_track_data = {
                    "artistName": itunes_artist_name,
                    "trackCensoredName": local_track_name,
                    "trackNumber": track_number,
                    "trackCount": local_track_count
                }

                custom_track = itunespy.track.result_item.ResultItem(custom_track_data)
                updated_track_list.append(custom_track)

        for i, track in enumerate(updated_track_list):
            track.track_number = i + 1

        itunes_collection._track_list = updated_track_list
        itunes_collection.track_count = len(updated_track_list)

        return itunes_collection

    def ask_to_organize_folder(self):
        console.print("[b][orchid]Do you wish to organize this folder?[/orchid][/b]", end="")
        confirm_prompt = BoldPrompt(color="orchid")
        confirm = console.input(confirm_prompt).lower()
        if confirm == "y":
            return True
        elif confirm == "n":
            return False
        else:
            console.print("[b][red]Invalid input, please enter [gold1]'y'[/gold1] or [gold1]'n'[/gold1].[/red][/b]")
            return self.ask_to_organize_folder()

    def replace_censored_text(self, text):
        censored_words = {}
        with open(self.censored_words_file, "r") as f:
            for line in f:
                censored_word, uncensored_word = line.strip().split(":")
                censored_words[censored_word] = uncensored_word

        for censored_word in censored_words:
            uncensored_word = censored_words[censored_word]
            text = text.replace(censored_word, uncensored_word)
        return text

    def handle_missing_tracks(self, itunes_collection, local_tracks):
        console.print("\n[b][orchid]Do you want to fill in the [gold1]missing tracks[/gold1] to the [gold1]iTunes collection?[/gold1][/orchid][/b]", end="")
        add_tracks = console.input(BoldPrompt(color="orchid")).lower()
        if add_tracks == "y":
            itunes_collection = self.add_custom_tracks(itunes_collection, local_tracks)

            console.print("\n[b][gold1]Updated iTunes tracks:[/gold1][/b]")
            tracks_table = Table(show_header=True, box=box.ROUNDED, border_style="gold3")
            tracks_table.add_column("#", justify="right")
            tracks_table.add_column("Track")

            for itunes_track in itunes_collection.get_tracks():
                tracks_table.add_row(str(itunes_track.track_number), f"[gold1]{self.replace_censored_text(itunes_track.track_censored_name)}[/gold1]")

            console.print(tracks_table)
            console.print(end="")

    def confirm_itunes_collection(self, itunes_collections, local_tracks):
        while True:
            console.print("\n[b][gold1]Is this the correct iTunes collection?[/gold1][/b]", end="")
            itunes_prompt = BoldPrompt(color="gold1")
            correct = console.input(itunes_prompt).lower()
            if correct == "y":
                return itunes_collections[0], True
            elif correct == "n":
                return self.handle_collection_selection(itunes_collections, local_tracks)
            else:
                console.print("[b][red]Invalid input, please enter [gold1]'y'[/gold1] or [gold1]'n'[/gold1].[/red][/b]")

    def handle_search_input(self):
        while True:
            search_term = console.input("\n[b][gold1]Enter the correct iTunes collection name or [orchid]'s'[/orchid] to skip:[/gold1][/b] ").rstrip()
            if search_term.lower() == "s":
                return None
            try:
                itunes_collections = itunespy.search_album(search_term)
            except LookupError:
                itunes_collections = []

            if not itunes_collections:
                console.print("[b][red]The iTunes collection you are looking for could not be found.[/red] [gold1]Please check the spelling and try again.[/gold1][/b]")
            else:
                self.print_itunes_tags(itunes_collections[0])
                return itunes_collections

    def search_itunes_collection(self, local_tracks):
        itunes_collection = None
        local_artist_name, local_collection_name, _, _ = self.get_local_tags(local_tracks)

        while True:
            try:
                itunes_collections = itunespy.search_album(f"{local_artist_name} {local_collection_name}")
            except LookupError:
                itunes_collections = []
            if not itunes_collections:
                self.print_local_tags(local_tracks)
                itunes_collections = self.handle_search_input()
                if itunes_collections is None:
                    return None, False
            else:
                self.print_local_tags(local_tracks)
                self.print_itunes_tags(itunes_collections[0])

            itunes_collection, confirm = self.confirm_itunes_collection(itunes_collections, local_tracks)
            if confirm:
                itunes_track_count = itunes_collection.track_count
                local_track_count = len(local_tracks)
                if itunes_track_count < local_track_count:
                    self.handle_missing_tracks(itunes_collections[0], local_tracks)
                return itunes_collection, confirm
            elif itunes_collections and not confirm:
                return None, False

    def find_audio_files(self, collection_path):
        local_tracks = []
        for root, dirs, files in os.walk(collection_path):
            files.sort()
            for file in files:
                if file.endswith(".flac") or file.endswith(".mp3"):
                    local_tracks.append(os.path.join(root, file))
        return local_tracks

    def itunesify(self):
        for artist_dir in os.listdir(self.music_directory):
            if artist_dir.startswith("."):
                continue
            artist_path = os.path.join(self.music_directory, artist_dir)
            for collection_dir in sorted(os.listdir(artist_path)):
                if collection_dir.startswith("."):
                    continue
                collection_path = os.path.join(artist_path, collection_dir)
                local_tracks = self.find_audio_files(collection_path)
                if "Albums" in collection_path or "Singles & EPs" in collection_path:
                    continue
                itunes_collection, confirm = self.search_itunes_collection(local_tracks)
                if itunes_collection is None:
                    continue
                elif confirm:
                    organize_folder = self.ask_to_organize_folder()
                    if not organize_folder:
                        continue

                    self.retag_files(local_tracks, itunes_collection)
                    self.save_itunes_cover(collection_path, itunes_collection)
                    self.move_files(local_tracks, self.replace_censored_text(itunes_collection.collection_censored_name), itunes_collection.parsed_release_date.year, collection_path, artist_path)
                    self.display_success_message(itunes_collection, self.get_file_type(local_tracks[0]).upper())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="iTunesify your music collection.")
    parser.add_argument("-d", "--directory", help="Specify the music directory to iTunesify.")
    parser.add_argument("-c", "--config", help="Specify a custom config file.", default="config.json")
    args = parser.parse_args()

    install()
    console = Console()

    itunesify = iTunesify(args.directory, args.config)
    itunesify.itunesify()
