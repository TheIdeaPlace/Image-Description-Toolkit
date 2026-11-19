"""
Batch Progress Dialog for ImageDescriber

Phase 3: Real-time batch processing progress dialog with pause/resume/stop controls.

This modeless dialog shows:
- Processing statistics (current/total, average time)
- Current image being processed
- Progress bar
- Control buttons (Pause/Resume, Stop, Close)

Accessibility:
- Uses wx.ListBox for single tab stop stats display
- Named controls for screen reader context
- Large click targets for buttons
"""

import wx
from pathlib import Path
from typing import Optional

#: The stopping state's line, and the text that identifies its row (see
#: update_progress, which keeps it selected through rebuilds).
STOPPING_PREFIX = "Stopping:"
STOPPING_LINE = f"{STOPPING_PREFIX} finishing the current video or save…"


def _row_label(row: str) -> str:
    """A stats row's label ("Items Processed" in "Items Processed:   3 / 9"),
    or the whole row when it has none ("Token Usage")."""
    label, sep, _ = row.partition(":")
    return label.strip() if sep else row


def _is_stopping_row(row: str) -> bool:
    """The Stopping row, as mark_stopping appends it or a rebuild shows it.
    Matched on the whole line, not "Stopping:" anywhere, so a file name or a
    description containing that word is never mistaken for it."""
    return row.endswith(STOPPING_LINE)


def say_without_moving_focus(window, text: str) -> None:
    """Have the screen reader say ``text`` through ``window`` without moving
    focus; a beep where that can't be done (macOS, Windows before 1709)."""
    try:
        from shared.uia_notify import notify
    except ImportError:
        notify = None
    try:
        if notify and window and notify(window.GetHandle(), text,
                                        activity_id="idt-batch-complete"):
            return
    except RuntimeError:        # wrapped C++ object deleted
        pass
    wx.Bell()


def _focus_if_alive(window) -> None:
    """Focus a window that may have been closed in the meantime."""
    try:
        if window:
            window.SetFocus()
    except RuntimeError:        # wrapped C++ object deleted
        pass


# "claude-code" -> "Claude Code". idt_core imports the same way in dev and
# frozen builds, so no try/except fallback is needed.
from idt_core.providers.registry import display_name as _display_provider  # noqa: E402
# "claude-haiku-5-5" -> "Claude Haiku 5.5": the name is what's spoken.
from idt_core.providers.catalog import model_display_name as _display_model  # noqa: E402
from idt_core.pricing import format_dollars as _dollars  # noqa: E402

#: Why a model has no price, as said in the cost row.
_COST_NOTE_WORDS = {
    "no charge": "no charge (runs on your computer)",
    "Ollama plan": "covered by your Ollama plan",
    "your plan": "covered by your Claude plan",
    "no price": "no price known for this model",
}


def cost_rows(token_stats: dict, total: int, extracting: bool = False,
              current: int = 0) -> list:
    """The batch's cost meter, as rows for the progress list: what the
    pictures described so far cost, the average per picture, and what the
    whole batch should come to: the cost so far, exactly, plus the average
    for each item still to go. List prices, so they're estimates."""
    cost = token_stats.get("cost")
    if cost is None:
        note = token_stats.get("cost_note")
        if not note:
            return []
        return [f"  Estimated Cost:           {_COST_NOTE_WORDS.get(note, note)}"]
    rows = [f"  Estimated Cost So Far:    {_dollars(cost)}"]
    avg = token_stats.get("avg_cost")
    if avg is not None:
        rows.append(f"  Average Cost per Image:   {_dollars(avg)}")
        # Not while videos are still extracting: the total leaves out frames
        # still to come, as with the time estimate.
        if total > 0 and not extracting:
            projected = cost + avg * max(total - current, 0)
            rows.append(f"  Projected Batch Cost:     about {_dollars(projected)}")
    return rows


class BatchProgressDialog(wx.Dialog):
    """Modeless dialog showing batch processing progress and controls"""
    
    def __init__(self, parent, total_images: int,
                 batch_provider: str = '', batch_model: str = '', batch_prompt: str = '',
                 describing: bool = False):
        """Initialize batch progress dialog

        Args:
            parent: Parent window (ImageDescriberFrame)
            total_images: Total number of images to process
            batch_provider: AI provider name shown in Job Settings section
            batch_model: AI model name shown in Job Settings section
            batch_prompt: Prompt style shown in Job Settings section
            describing: The window follows a batch of descriptions from the
                start, with no stages (a resumed batch, frames, downloaded
                images), so its title counts images described. A run with
                stages says so through its "Describing" stage instead.
        """
        wx.Dialog.__init__(
            self,
            parent,
            title="Batch Processing Progress",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP  # Modeless, resizable, always visible
        )
        
        self.parent_window = parent
        self.total_images = total_images
        self.batch_provider = batch_provider
        self.batch_model = batch_model
        self.batch_prompt = batch_prompt
        self._is_complete = False  # Set by mark_complete(); changes Stop→Close
        # Images that failed in this batch. Shown here rather than as one
        # modal error box per image, which a large failing batch stacked by the
        # hundred over the dialog.
        self.failed_count = 0
        self.last_failure = ''
        # Set by mark_stopping: later stages and progress keep saying so.
        self._stopping = False

        # Stage tracking — a run moves through Extracting → Saving → Describing,
        # each with its own item count.  begin_stage() resets the counter and bar
        # so progress reads per stage rather than as one merged total.
        self.stage_name = ''
        self.stage_index = 0
        self.stage_count = 0
        self._describing = describing
        # "45%, 9 of 20 images described", put at the front of the title
        # while images are being described (#412). None otherwise.
        self._title_progress = None
        # Describing waits for the next video's frames (#352); see
        # show_waiting_for_frames.
        self._waiting = False
        # Frame extraction running alongside describing (#344): its own row,
        # so the describe counts never overwrite it. None when not extracting.
        self._extraction = None
        # The last update_progress arguments, so an extraction tick can
        # rebuild the list without losing the describe progress.
        self._last_progress = None

        # Create UI
        self._create_ui()
        
        # Set initial size
        self.SetSize((500, 420))
        self.CenterOnParent()
    
    def _create_ui(self):
        """Create dialog UI components"""
        # Main panel
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Title label
        title_label = wx.StaticText(
            panel,
            label="Processing Statistics:",
            name="Processing statistics title"
        )
        title_font = title_label.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title_label.SetFont(title_font)
        main_sizer.Add(title_label, 0, wx.ALL, 10)
        
        # Stats list box (read-only, single-selection for accessibility)
        # Includes current image as last item for keyboard navigation
        self.stats_list = wx.ListBox(
            panel,
            style=wx.LB_SINGLE,
            name="Processing statistics and current image"
        )
        self.stats_list.SetMinSize((450, 160))
        # No separator rows: lines of "─" were list items, and a screen reader
        # read them aloud (#427). Every row says something.
        main_sizer.Add(self.stats_list, 0, wx.ALL | wx.EXPAND, 10)
        
        # Progress label (kept: it says when the bar can't show a percentage)
        self.progress_label = progress_label = wx.StaticText(
            panel,
            label="Progress:",
            name="Progress label"
        )
        main_sizer.Add(progress_label, 0, wx.LEFT | wx.RIGHT, 10)
        
        # Progress bar
        self.progress_bar = wx.Gauge(
            panel,
            range=100,
            name="Batch progress percentage"
        )
        self.progress_bar.SetMinSize((-1, 25))
        main_sizer.Add(self.progress_bar, 0, wx.ALL | wx.EXPAND, 10)
        
        # Button sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Pause/Resume button
        self.pause_button = wx.Button(panel, label="Pause", size=(100, -1))
        self.pause_button.Bind(wx.EVT_BUTTON, self.on_pause_clicked)
        button_sizer.Add(self.pause_button, 0, wx.ALL, 5)
        
        # Stop button
        self.stop_button = wx.Button(panel, label="Stop", size=(100, -1))
        self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop_clicked)
        button_sizer.Add(self.stop_button, 0, wx.ALL, 5)
        
        # Close button
        self.close_button = wx.Button(panel, label="Close", size=(100, -1))
        self.close_button.Bind(wx.EVT_BUTTON, lambda e: self.Hide())
        button_sizer.Add(self.close_button, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        # Set panel sizer
        panel.SetSizer(main_sizer)
        
        # Dialog sizer
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        # Escape, Alt+F4 and the title bar close a finished window the way its
        # Close button does (destroy, focus back to the image list); before it
        # finishes they hide it, as they always did (#438 review). Escape needs
        # its own hook: this dialog has no Cancel button, so wx ignored it
        # (found under NVDA in the test VM).
        self.Bind(wx.EVT_CLOSE, self._on_close_event)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE and getattr(self, '_is_complete', False):
            self.on_stop_clicked(event)
            return
        event.Skip()

    def _on_close_event(self, event):
        if getattr(self, '_is_complete', False):
            self.on_stop_clicked(event)
        else:
            event.Skip()

    def begin_stage(self, name: str, total: int,
                    stage_index: int = 0, stage_count: int = 0,
                    can_interrupt: bool = True, can_stop=None):
        """Start a new stage, resetting the item counter and progress bar.

        A run moves through up to three stages (Extracting frames, Saving
        workspace, Describing).  Each gets its own 0..total count rather than
        being merged into one bar, so "40 of 200" always means "within this
        stage".

        Args:
            name: Stage label, e.g. "Extracting frames"
            total: Number of items in this stage
            stage_index: 1-based position of this stage (0 = don't show)
            stage_count: Total number of stages in the run (0 = don't show)
            can_interrupt: Whether Pause/Stop apply.  Only the describe stage
                runs under BatchProcessingWorker, so the copy/extract stages
                pass False and the buttons are disabled.
            can_stop: Override for Stop alone. The extract and save stages
                of a run can be stopped (the run is cancelled before
                describing) though they cannot be paused. None = can_interrupt.
        """
        self.stage_name = name
        self.total_images = total
        self.stage_index = stage_index
        self.stage_count = stage_count

        self.progress_bar.SetValue(0)
        self.pause_button.Enable(can_interrupt)
        self.stop_button.Enable(can_interrupt if can_stop is None else can_stop)

        # update_progress sets the title, once, with this stage's progress.
        self.update_progress(0, total)

    def _set_stage_title(self):
        """Title carries the stage so screen readers announce the transition
        when the dialog is the active window. While stopping, the save that
        finishes the stop must not read as the batch's next step."""
        name = self.stage_name
        if self._is_complete:
            return              # mark_complete's title stays
        if self._stopping:
            title = (f"{STOPPING_PREFIX} {name.lower()} — Batch Processing"
                     if name else "Stopping — Batch Processing")
        elif name and self.stage_index and self.stage_count:
            title = f"{name} (step {self.stage_index} of {self.stage_count}) — Batch Processing"
        elif name:
            title = f"{name} — Batch Processing"
        else:
            title = "Batch Processing Progress"
        if self._title_progress and not self._stopping:
            # Progress first: Insert+T (read title) is how a screen reader
            # user checks how far a batch has got (#412).
            title = f"{self._title_progress} — {title}"
        if self.GetTitle() != title:     # each change can be spoken
            self.SetTitle(title)

    def _is_describing(self) -> bool:
        if self.stage_name:
            return self.stage_name.lower().startswith("describing")
        return self._describing

    def _progress_title(self, current: int, total: int, on_an_image: bool):
        """ "45%, 9 of 20 images described", or None outside describing.

        ``current`` is the image being described, so one fewer is done; one
        that failed isn't described, and the percentage is of the same count.
        While videos are still extracting the total grows, so no percentage
        (it would fall as videos finish). The stage name says so before
        begin_extraction has run, so the title doesn't flash a percentage."""
        if not self._is_describing():
            return None
        done = max(current - 1, 0) if on_an_image else current
        described = max(done - self.failed_count, 0)
        if (total <= 0 or self._extraction is not None
                or "extracting" in self.stage_name.lower()):
            return f"{described:,} images described so far"
        percent = int(described * 100 / total)
        return f"{percent}%, {described:,} of {total:,} images described"

    # ----- frame extraction alongside describing (#344) ----- #

    def begin_extraction(self, total_videos: int) -> None:
        """Videos are being extracted while describing runs: show a row for it."""
        self._extraction = {"done": 0, "total": total_videos, "name": ""}
        self._rebuild()

    def set_extraction(self, done: int, total: int, name: str = "") -> None:
        """One more video extracted. Ignored once extraction has ended."""
        if self._extraction is None:
            return
        self._extraction = {"done": done, "total": total, "name": name}
        self._rebuild()

    def show_waiting_for_frames(self) -> None:
        """Describing has caught up with extraction: say so in place of the
        last image, which was no longer being described. Shown on the same
        "Current Image" row, so a reader on it stays there; cleared by the
        next image, the end of extraction, or the end of the batch."""
        if self._last_progress is None:
            return
        self._waiting = True
        args = dict(self._last_progress)
        args.update(file_path=None, image_name=None)
        self.update_progress(**args)

    def stop_extraction(self) -> None:
        """Extraction was stopped (Stop, a halt): drop its row so the final
        stats don't still say videos are being extracted. No title change:
        whatever ends the batch sets that."""
        if self._extraction is None:
            return
        self._extraction = None
        self._rebuild()

    def end_extraction(self, stage_name: str = "Describing") -> None:
        """Extraction finished: drop its row and say so in the title, once,
        rather than on every tick (each title change is spoken)."""
        if self._extraction is None:
            return
        self._extraction = None
        self.stage_name = stage_name
        if self._last_progress is None:
            self._set_stage_title()
        else:
            self._rebuild()     # sets the title too, with the progress

    def _rebuild(self) -> None:
        if self._last_progress is not None:
            self.update_progress(**self._last_progress)

    def _set_progress_label(self, text: str) -> None:
        # The gauge's accessible name comes from this label on Windows
        # (measured through MSAA); wx's SetName on the gauge isn't exposed.
        if self.progress_label.GetLabel() != text:
            self.progress_label.SetLabel(text)

    def note_completed(self, last_image: str, last_description: str,
                       token_stats: dict = None) -> None:
        """An image was described. Kept for the next rebuild, not shown now:
        the next image's progress update shows it, as it always has. The last
        image of a batch has no next update, so without this mark_complete
        rebuilt from the stats before it, and the summary left it out of "Last
        Image Described", the token totals and the cost (#475)."""
        if self._last_progress is None:
            return
        self._last_progress.update(last_image=last_image,
                                   last_description=last_description)
        if token_stats is not None:
            self._last_progress["token_stats"] = token_stats

    def note_failure(self, image_name: str, error: str) -> None:
        """Count a failed image; shown on the next progress update."""
        self.failed_count += 1
        self.last_failure = f"{image_name}: {error}"

    def update_progress(self, current: int, total: int,
                       file_path: str = None, avg_time: float = 0.0,
                       image_name: str = None, provider: str = None, model: str = None,
                       last_image: str = None, last_description: str = None,
                       token_stats: dict = None,
                       batch_provider: str = None, batch_model: str = None,
                       batch_prompt: str = None,
                       status_message: str = None):
        """Update progress display
        
        Args:
            current: Current image number (1-based)
            total: Total number of images
            file_path: Path to current image being processed (optional)
            avg_time: Average processing time per image in seconds (optional)
            image_name: Display name override (for video extraction, optional)
            provider: AI provider name (for video extraction, optional)
            model: AI model name (for video extraction, optional)
            last_image: Last image that was described (optional)
            last_description: Full description text of last image (optional, not clipped)
            token_stats: Dict with avg_input, avg_output, avg_total, total,
                         peak_total, peak_name (optional, shown when non-None)
            batch_provider: Override stored batch provider (optional)
            batch_model: Override stored batch model (optional)
            batch_prompt: Override stored batch prompt (optional)
            status_message: Optional status line shown at the top of the list
                (e.g. "Loading MLX model…"). Cleared automatically when None.
        """
        self._last_progress = dict(
            current=current, total=total, file_path=file_path, avg_time=avg_time,
            image_name=image_name, provider=provider, model=model,
            last_image=last_image, last_description=last_description,
            token_stats=token_stats, status_message=status_message)
        # Allow callers to update stored batch settings
        if batch_provider is not None:
            self.batch_provider = batch_provider
        if batch_model is not None:
            self.batch_model = batch_model
        if batch_prompt is not None:
            self.batch_prompt = batch_prompt

        # Save selection before clearing so we can restore it after rebuild
        saved_selection = self.stats_list.GetSelection()
        # Restored by the row's label, not its number: rows come and go above
        # it (a video finishing, extraction ending, a first failure), and an
        # index left a screen reader user on a different row (#344 review).
        saved_label = (_row_label(self.stats_list.GetString(saved_selection))
                       if saved_selection != wx.NOT_FOUND else None)
        # The stopping line moves (mark_stopping appends it at the end; the
        # rebuild puts it at the top), so follow it by text, not by row.
        on_stopping_line = (
            self._stopping and saved_selection != wx.NOT_FOUND
            and _is_stopping_row(self.stats_list.GetString(saved_selection)))

        # Rebuild stats list
        self.stats_list.Clear()

        # While stopping, every rebuild keeps saying so (it used to be wiped by
        # the first progress tick after Stop), alongside any caller's own status.
        status_lines = [STOPPING_LINE] if self._stopping else []
        if status_message and status_message != STOPPING_LINE:
            status_lines.append(status_message)

        # ── Optional status message (e.g. MLX model loading / download) ─────
        if status_lines:
            for line in status_lines:
                self.stats_list.Append(f"⏳ Status:                   {line}")

        # ── Processing Progress section ──────────────────────────────────────
        if self.stage_name:
            if self.stage_index and self.stage_count and not self._stopping:
                stage_label = f"{self.stage_name} (step {self.stage_index} of {self.stage_count})"
            else:
                stage_label = self.stage_name
            self.stats_list.Append(f"Stage:                      {stage_label}")
        # While videos are still being extracted the total grows as each one
        # finishes; say so rather than let it read as the whole batch.
        more = "  (more as videos finish)" if self._extraction is not None else ""
        if total > 0:
            self.stats_list.Append(f"Items Processed:            {current} / {total}{more}")
        else:
            # total == 0 means "unknown length" (e.g. consuming a generator);
            # show a running count rather than a meaningless "N / 0".
            self.stats_list.Append(f"Items Processed:            {current}{more}")
        if self._extraction is not None:
            ex = self._extraction
            self.stats_list.Append(
                f"Extracting Frames:          {ex['done']:,} of {ex['total']:,} videos")
            if ex["name"]:
                self.stats_list.Append(f"Last Video Extracted:       {ex['name']}")

        if self.failed_count:
            self.stats_list.Append(f"Failed:                     {self.failed_count}")
            self.stats_list.Append(f"Last Failure:               {self.last_failure}")

        if avg_time > 0:
            self.stats_list.Append(f"Average Processing Time:    {avg_time:.1f} seconds")

        # Not while videos are still extracting: the total so far leaves out
        # every frame still to come, so the estimate was far too short, and
        # the row vanished whenever describing caught up (#352).
        if avg_time > 0 and current < total and self._extraction is None:
            remaining_images = total - current
            estimated_seconds = remaining_images * avg_time
            if estimated_seconds < 60:
                time_str = f"{estimated_seconds:.0f} seconds"
            elif estimated_seconds < 3600:
                time_str = f"{estimated_seconds / 60:.1f} minutes"
            else:
                time_str = f"{estimated_seconds / 3600:.1f} hours"
            self.stats_list.Append(f"Estimated Time Remaining:   {time_str}")

        # ── Job Settings section ─────────────────────────────────────────────
        if self.batch_provider or self.batch_model or self.batch_prompt:
            if self.batch_provider:
                self.stats_list.Append(f"Provider:                   {_display_provider(self.batch_provider)}")
            if self.batch_model:
                self.stats_list.Append(f"Model:                      "
                                       f"{_display_model(self.batch_provider, self.batch_model)}")
            if self.batch_prompt:
                self.stats_list.Append(f"Prompt Style:               {self.batch_prompt}")

        # ── Token Usage section (only when data is available) ────────────────
        if token_stats:
            self.stats_list.Append("Token Usage")
            for row in cost_rows(token_stats, total, extracting=self._extraction is not None,
                                 current=current):
                self.stats_list.Append(row)
            self.stats_list.Append(f"  Average Input Tokens:     {token_stats['avg_input']:,}")
            self.stats_list.Append(f"  Average Output Tokens:    {token_stats['avg_output']:,}")
            self.stats_list.Append(f"  Average Total Tokens:     {token_stats['avg_total']:,}")
            self.stats_list.Append(f"  Total Tokens:             {token_stats['total']:,}")
            peak_label = f"{token_stats['peak_total']:,} ({token_stats['peak_name']})"
            self.stats_list.Append(f"  Largest Token Use:        {peak_label}")

        # ── Last completed + current image ───────────────────────────────────
        if last_image and last_description:
            self.stats_list.Append(f"Last Image Described:       {last_image}")
            self.stats_list.Append(f"Last Description:           {last_description}")

        if image_name or file_path:
            self._waiting = False
        if image_name:
            self.stats_list.Append(f"Current:                    {image_name}")
            if provider and model:
                self.stats_list.Append(f"Provider:                   {_display_provider(provider)}")
                self.stats_list.Append(f"Model:                      {_display_model(provider, model)}")
        elif file_path:
            self.stats_list.Append(f"Current Image:              {Path(file_path).name}")
        elif self._waiting and self._extraction is not None:
            self.stats_list.Append("Current Image:              "
                                   "(waiting for the next video's frames)")

        # Update progress bar — pulse when the total is unknown. It is not
        # known while videos are extracting either: the total grows as each
        # one finishes, so a percentage fell (100% then 50%), and screen
        # readers announce the gauge's changes (#352).
        if total > 0 and self._extraction is None:
            self.progress_bar.SetValue(int((current / total) * 100))
            self._set_progress_label("Progress:")
        else:
            self.progress_bar.Pulse()
            # A pulsing gauge keeps its last value (0), so a screen reader
            # reviewing it read "0%" all through extraction. Say why instead.
            self._set_progress_label("Progress: total not known yet")

        self._title_progress = self._progress_title(
            current, total, on_an_image=bool(file_path or image_name))
        self._set_stage_title()

        # Restore the previously selected row
        count = self.stats_list.GetCount()
        stopping_row = wx.NOT_FOUND
        if on_stopping_line:
            # Found by its text rather than assumed to be row 0, so the
            # selection follows it if the rows above it ever change.
            stopping_row = next((i for i in range(count)
                                 if _is_stopping_row(self.stats_list.GetString(i))),
                                wx.NOT_FOUND)
        label_row = wx.NOT_FOUND
        if stopping_row == wx.NOT_FOUND and saved_label:
            same = [i for i in range(count)
                    if _row_label(self.stats_list.GetString(i)) == saved_label]
            if same:
                # Rows can share a label (two status lines); take the one
                # nearest where the reader was.
                label_row = min(same, key=lambda i: abs(i - saved_selection))
        if stopping_row != wx.NOT_FOUND:
            self.stats_list.SetSelection(stopping_row)
            self.stats_list.EnsureVisible(stopping_row)
        elif label_row != wx.NOT_FOUND:
            self.stats_list.SetSelection(label_row)
            self.stats_list.EnsureVisible(label_row)
        elif saved_selection != wx.NOT_FOUND and count > 0:
            idx = min(saved_selection, count - 1)
            self.stats_list.SetSelection(idx)
            self.stats_list.EnsureVisible(idx)

        self.Layout()
    
    def on_pause_clicked(self, event):
        """Toggle pause/resume"""
        if self.pause_button.GetLabel() == "Pause":
            # Call parent's pause handler
            if hasattr(self.parent_window, 'on_pause_batch'):
                self.parent_window.on_pause_batch()
            self.pause_button.SetLabel("Resume")
        else:
            # Call parent's resume handler
            if hasattr(self.parent_window, 'on_resume_batch'):
                self.parent_window.on_resume_batch()
            self.pause_button.SetLabel("Pause")
    
    def on_stop_clicked(self, event):
        """Stop processing — or close the dialog when batch is already complete."""
        if self._is_complete:
            parent = self.parent_window
            self.Destroy()
            # Back to where the user works, as focus_completion took it away (#409).
            image_list = getattr(parent, 'image_list', None)
            if image_list:
                wx.CallAfter(_focus_if_alive, image_list)
            return

        # Import here to avoid circular dependency
        from shared.wx_common import ask_yes_no

        # Confirm before stopping
        result = ask_yes_no(
            self,
            "Stop batch processing?\n\n"
            "Progress will be saved. You can resume later by reopening this workspace."
        )

        if result:
            # Call parent's stop handler
            if hasattr(self.parent_window, 'on_stop_batch'):
                self.parent_window.on_stop_batch()

    def mark_stopping(self):
        """Stop was pressed while frames were extracting or the workspace was
        saving: that work finishes its current step first. Say so in the window
        (and its title, which a screen reader announces) instead of closing it,
        so the wait isn't silent; Stop and Pause no longer apply."""
        self._stopping = True
        # Its Close button only hides it. Focus moved into a hidden window
        # went nowhere for the whole save, so bring it back first.
        if not self.IsShown():
            self.Show()
        self.Raise()
        # Focus before disabling: disabling the focused Stop button moves
        # focus to Close, where a second Enter or Escape hid the window.
        self.stats_list.SetFocus()
        self.pause_button.Enable(False)
        self.stop_button.Enable(False)
        # Called again (Stop, then a cancelled close): go back to the line
        # already there rather than adding a second one.
        row = next((i for i in range(self.stats_list.GetCount())
                    if _is_stopping_row(self.stats_list.GetString(i))), wx.NOT_FOUND)
        if row == wx.NOT_FOUND:
            self.stats_list.Append(STOPPING_LINE)
            row = self.stats_list.GetCount() - 1
        self.stats_list.SetSelection(row)
        self.stats_list.EnsureVisible(row)
        # The same title begin_stage gives a stage begun while stopping.
        self._set_stage_title()

    def mark_complete(self, summary: str = "", stopped: bool = False):
        """
        Called when batch processing finishes naturally — keeps dialog open
        so the user can review stats before dismissing.

        Changes Pause→disabled, Stop→Close, updates title to show completion.
        """
        self._is_complete = True
        # Nothing is current any more: no "Current" or "waiting" row above
        # the summary.
        self._waiting = False
        if self._last_progress is not None:
            self._last_progress.update(file_path=None, image_name=None)
        # Redraw first: a failure noted after the last progress update (the
        # batch's last image failing) was counted in the summary below but
        # not in the stats, which read "Failed: 3" over "4 failed".
        self._rebuild()
        # Late extraction ticks must not rebuild the list over the summary.
        self._extraction = None
        self._last_progress = None

        # Append completion notice to the live stats list
        # stopped: the batch ended itself before the last image (e.g. the
        # provider is signed out). Say so; the title is what a screen
        # reader announces, and "Complete" would be wrong.
        self.stats_list.Append("Batch stopped" if stopped else "\u2713  Batch Complete!")
        if summary:
            self.stats_list.Append(f"     {summary}")
        self.stats_list.EnsureVisible(self.stats_list.GetCount() - 1)

        # Fill progress bar (a stopped batch keeps the progress it made)
        if not stopped:
            self.progress_bar.SetValue(100)

        # Update controls
        self.pause_button.SetLabel("Pause")
        self.pause_button.Enable(False)
        self.stop_button.SetLabel("Close")
        self.stop_button.Enable(True)

        # Hide the redundant original Close button (Stop is now the only Close)
        self.close_button.Hide()
        self.Layout()

        # Update window title so screen readers announce completion
        self.SetTitle("Batch Stopped  —  Review stats then close" if stopped
                      else "Batch Complete  —  Review stats then close")

    def focus_completion(self):
        """Bring the finished window forward with focus on its summary line.

        A screen reader then says the "Batch Complete" title and the summary.
        The main window used to take focus right after the batch ended, so the
        retitle above was never heard (#409, NVDA bug bash 11/15/2026).
        """
        if not self or not self.IsShown():
            return
        active = wx.GetActiveWindow()
        if not self.IsEnabled() or (active is not None and active not in (self, self.GetParent())):
            # Another window has the user (a modal one, such as the chat window,
            # disables this one): don't pull focus out of it. Say it instead.
            say_without_moving_focus(active or self, self._completion_words())
            return
        self.Raise()
        last = self.stats_list.GetCount() - 1
        if last >= 0:
            self.stats_list.SetSelection(last)
        self.stats_list.SetFocus()

    def _completion_words(self) -> str:
        """ "Batch Complete" (or Stopped) and the summary line, for an announcement."""
        last = self.stats_list.GetCount() - 1
        summary = self.stats_list.GetString(last).strip() if last >= 0 else ""
        title = self.GetTitle().split("—")[0].strip()
        return f"{title}. {summary}" if summary else title

    def reset_pause_button(self):
        """Reset pause button to 'Pause' state"""
        self.pause_button.SetLabel("Pause")
