"""Projects dashboard screen."""

from __future__ import annotations 

from dataclasses import dataclass 
from pathlib import Path 

from PyQt6 .QtCore import Qt ,pyqtSignal 
from PyQt6 .QtGui import QColor ,QBrush 
from PyQt6 .QtWidgets import (
QBoxLayout ,
QCheckBox ,
QComboBox ,
QDialog ,
QDialogButtonBox ,
QFileDialog ,
QFrame ,
QHBoxLayout ,
QHeaderView ,
QLabel ,
QLineEdit ,
QPushButton ,
QScrollArea ,
QSizePolicy ,
QTableWidget ,
QTableWidgetItem ,
QTextEdit ,
QVBoxLayout ,
QWidget ,
)

from gme_app .models import AudioProvider ,ProcessingRun ,Project ,UserProfile ,format_datetime 
from gme_app .ui .camera_record_dialog import CameraRecordDialog 
from gme_app .ui .widgets import MetricCard ,ProjectCard ,ResponsiveGrid ,run_status_label 


@dataclass (slots =True )
class CreateProjectPayload :
    title :str 
    description :str 
    video_path :str 
    start_processing :bool 
    model_name :str 
    detector_name :str 
    processing_mode :str 
    audio_provider :str 


class CreateProjectDialog (QDialog ):
    def __init__ (
    self ,
    *,
    models :list [str ],
    detectors :list [str ],
    audio_providers :list [AudioProvider ],
    camera_output_dir :Path ,
    parent :QWidget |None =None ,
    )->None :
        super ().__init__ (parent )
        self .setWindowTitle ("Create Project")
        self .setModal (True )
        self .resize (680 ,470 )

        self .models =[item .strip ()for item in models if item .strip ()]
        self .detectors =[item .strip ()for item in detectors if item .strip ()]
        self .audio_providers =[item for item in audio_providers if item .code ]
        self .camera_output_dir =camera_output_dir 
        self ._build_ui ()

    def _build_ui (self )->None :
        layout =QVBoxLayout (self )
        layout .setContentsMargins (18 ,18 ,18 ,18 )
        layout .setSpacing (10 )

        title_label =QLabel ("Project Title")
        self .title_input =QLineEdit ()
        self .title_input .setPlaceholderText ("Example: Interview_01")

        description_label =QLabel ("Description")
        self .description_input =QTextEdit ()
        self .description_input .setPlaceholderText ("Describe the project goal briefly")
        self .description_input .setFixedHeight (110 )

        model_label =QLabel ("Analysis Model")
        self .model_combo =QComboBox ()
        self .model_combo .addItems (self .models )

        detector_label =QLabel ("Face Detector")
        self .detector_combo =QComboBox ()
        for detector in self .detectors :
            self .detector_combo .addItem (detector ,detector )

        processing_mode_label =QLabel ("Processing Mode")
        self .processing_mode_combo =QComboBox ()
        self .processing_mode_combo .addItem ("Video only","video_only")
        self .processing_mode_combo .addItem ("Audio only","audio_only")
        self .processing_mode_combo .addItem ("Audio + Video","audio_and_video")
        self .processing_mode_combo .currentIndexChanged .connect (self ._on_processing_mode_changed )

        audio_provider_label =QLabel ("Audio Provider")
        self .audio_provider_combo =QComboBox ()

        video_label =QLabel ("Video")
        file_row =QHBoxLayout ()
        file_row .setSpacing (8 )
        self .video_input =QLineEdit ()
        self .video_input .setReadOnly (True )
        self .video_input .setPlaceholderText ("Choose video file or record from camera")

        browse_button =QPushButton ("Choose File")
        browse_button .setObjectName ("SecondaryButton")
        browse_button .clicked .connect (self ._browse_video )

        camera_button =QPushButton ("Record Camera")
        camera_button .setObjectName ("SecondaryButton")
        camera_button .clicked .connect (self ._record_with_camera )

        file_row .addWidget (self .video_input ,1 )
        file_row .addWidget (browse_button )
        file_row .addWidget (camera_button )

        self .start_processing_checkbox =QCheckBox ("Start processing immediately")
        self .start_processing_checkbox .setChecked (True )

        self .error_label =QLabel ("")
        self .error_label .setObjectName ("ErrorLabel")
        self .error_label .hide ()

        self .button_box =QDialogButtonBox (QDialogButtonBox .StandardButton .Ok |QDialogButtonBox .StandardButton .Cancel )
        self .button_box .accepted .connect (self ._on_accept )
        self .button_box .rejected .connect (self .reject )

        ok_button =self .button_box .button (QDialogButtonBox .StandardButton .Ok )
        cancel_button =self .button_box .button (QDialogButtonBox .StandardButton .Cancel )
        if ok_button :
            ok_button .setText ("Create")
            ok_button .setObjectName ("PrimaryButton")
        if cancel_button :
            cancel_button .setText ("Cancel")
            cancel_button .setObjectName ("SecondaryButton")

        layout .addWidget (title_label )
        layout .addWidget (self .title_input )
        layout .addWidget (description_label )
        layout .addWidget (self .description_input )
        layout .addWidget (model_label )
        layout .addWidget (self .model_combo )
        layout .addWidget (detector_label )
        layout .addWidget (self .detector_combo )
        layout .addWidget (processing_mode_label )
        layout .addWidget (self .processing_mode_combo )
        layout .addWidget (audio_provider_label )
        layout .addWidget (self .audio_provider_combo )
        layout .addWidget (video_label )
        layout .addLayout (file_row )
        layout .addWidget (self .start_processing_checkbox )
        layout .addWidget (self .error_label )
        layout .addStretch (1 )
        layout .addWidget (self .button_box )
        self ._on_processing_mode_changed ()

    def _browse_video (self )->None :
        file_path ,_ =QFileDialog .getOpenFileName (
        self ,
        "Select Video",
        "",
        "Video (*.mp4 *.mov *.avi *.mkv);;All Files (*.*)",
        )
        if file_path :
            self .video_input .setText (file_path )

    def _record_with_camera (self )->None :
        dialog =CameraRecordDialog (output_dir =self .camera_output_dir ,parent =self )
        if dialog .exec ()==QDialog .DialogCode .Accepted and dialog .recorded_path is not None :
            self .video_input .setText (str (dialog .recorded_path ))

    def _on_accept (self )->None :
        self .error_label .hide ()

        title =self .title_input .text ().strip ()
        video_path =self .video_input .text ().strip ()
        model_name =self .model_combo .currentText ().strip ()
        detector_name =str (self .detector_combo .currentData ()or "").strip ().lower ()
        processing_mode =str (self .processing_mode_combo .currentData ()or "video_only").strip ().lower ()
        audio_provider_raw =str (self .audio_provider_combo .currentData ()or "").strip ().lower ()
        audio_provider =""if audio_provider_raw in {"","__none__"}else audio_provider_raw 

        if len (title )<3 :
            self ._show_error ("Title must be at least 3 characters.")
            return 
        if processing_mode in {"video_only","audio_and_video"}and not model_name :
            self ._show_error ("Select an analysis model.")
            return 
        if not video_path :
            self ._show_error ("Choose a video file.")
            return 
        if processing_mode in {"video_only","audio_and_video"}and not detector_name :
            self ._show_error ("Select a face detector.")
            return 
        if processing_mode in {"audio_only","audio_and_video"}and audio_provider_raw in {"","__none__"}:
            self ._show_error ("No compatible audio provider for this mode.")
            return 
        if not Path (video_path ).exists ():
            self ._show_error ("Selected video file was not found.")
            return 

        self .accept ()

    def _show_error (self ,message :str )->None :
        self .error_label .setText (message )
        self .error_label .show ()

    def _on_processing_mode_changed (self )->None :
        mode =str (self .processing_mode_combo .currentData ()or "video_only").strip ().lower ()
        video_enabled =mode in {"video_only","audio_and_video"}
        audio_enabled =mode in {"audio_only","audio_and_video"}
        self ._refresh_audio_providers_for_mode (mode )
        self .model_combo .setEnabled (video_enabled )
        self .detector_combo .setEnabled (video_enabled )
        has_compatible_audio_provider =str (self .audio_provider_combo .currentData ()or "")!="__none__"
        self .audio_provider_combo .setEnabled (audio_enabled and has_compatible_audio_provider )

    def _refresh_audio_providers_for_mode (self ,mode :str )->None :
        selected_code =str (self .audio_provider_combo .currentData ()or "").strip ().lower ()
        self .audio_provider_combo .blockSignals (True )
        self .audio_provider_combo .clear ()

        if mode =="audio_and_video":
            video_providers =[item for item in self .audio_providers if item .is_video_provider ]
            if video_providers :
                providers =video_providers 
            else :
                providers =[item for item in self .audio_providers if item .supports_video ]
        elif mode =="audio_only":
            providers =[item for item in self .audio_providers if item .supports_audio ]
        else :
            providers =[item for item in self .audio_providers if item .supports_audio or item .supports_video ]

        for provider in providers :
            self .audio_provider_combo .addItem (provider .title ,provider .code )

        if self .audio_provider_combo .count ()==0 :
            self .audio_provider_combo .addItem ("No suitable providers","__none__")

        if selected_code :
            selected_index =self .audio_provider_combo .findData (selected_code )
            if selected_index >=0 :
                self .audio_provider_combo .setCurrentIndex (selected_index )

        self .audio_provider_combo .blockSignals (False )

    def payload (self )->CreateProjectPayload :
        return CreateProjectPayload (
        title =self .title_input .text ().strip (),
        description =self .description_input .toPlainText ().strip (),
        video_path =self .video_input .text ().strip (),
        start_processing =self .start_processing_checkbox .isChecked (),
        model_name =self .model_combo .currentText ().strip (),
        detector_name =str (self .detector_combo .currentData ()or "").strip ().lower (),
        processing_mode =str (self .processing_mode_combo .currentData ()or "video_only").strip ().lower (),
        audio_provider =(
        ""
        if str (self .audio_provider_combo .currentData ()or "").strip ().lower ()in {"","__none__"}
        else str (self .audio_provider_combo .currentData ()or "").strip ().lower ()
        ),
        )


class DashboardView (QWidget ):
    refresh_requested =pyqtSignal ()
    logout_requested =pyqtSignal ()
    create_project_requested =pyqtSignal (str ,str ,str ,bool ,str ,str ,str ,str )
    open_project_requested =pyqtSignal (str )
    open_profile_requested =pyqtSignal ()
    open_admin_requested =pyqtSignal ()

    def __init__ (self ,parent :QWidget |None =None )->None :
        super ().__init__ (parent )
        self ._all_projects :list [Project ]=[]
        self ._runs_by_project :dict [str ,ProcessingRun |None ]={}
        self ._models :list [str ]=[]
        self ._detectors :list [str ]=[]
        self ._audio_providers :list [AudioProvider ]=[]
        self ._camera_output_dir =Path .cwd ()/"captures"
        self ._is_admin =False 
        self ._build_ui ()
        self ._apply_responsive_mode ()
        self .set_active_nav ("projects")

    def _build_ui (self )->None :
        root =QHBoxLayout (self )
        root .setContentsMargins (18 ,16 ,18 ,16 )
        root .setSpacing (14 )

        self .sidebar =self ._build_sidebar ()
        root .addWidget (self .sidebar ,0 )

        self .main_panel =QFrame ()
        self .main_panel .setObjectName ("MainPanel")
        self .main_panel .setSizePolicy (QSizePolicy .Policy .Expanding ,QSizePolicy .Policy .Expanding )
        main_layout =QVBoxLayout (self .main_panel )
        main_layout .setContentsMargins (16 ,16 ,16 ,16 )
        main_layout .setSpacing (12 )

        header =self ._build_header ()
        main_layout .addWidget (header ,0 )

        self .status_message =QLabel ("")
        self .status_message .setObjectName ("SectionHint")
        self .status_message .hide ()
        main_layout .addWidget (self .status_message )

        self .content_scroll =QScrollArea ()
        self .content_scroll .setWidgetResizable (True )
        self .content_scroll .setFrameShape (QFrame .Shape .NoFrame )

        content =QWidget ()
        content_layout =QVBoxLayout (content )
        content_layout .setContentsMargins (0 ,0 ,0 ,0 )
        content_layout .setSpacing (18 )

        self .metrics_layout =QBoxLayout (QBoxLayout .Direction .LeftToRight )
        self .metrics_layout .setSpacing (10 )
        self .total_metric =MetricCard ("Total Projects","0")
        self .active_metric =MetricCard ("Active","0")
        self .done_metric =MetricCard ("Completed","0")
        self .runs_metric =MetricCard ("With Last Run","0")
        self .metrics_layout .addWidget (self .total_metric )
        self .metrics_layout .addWidget (self .active_metric )
        self .metrics_layout .addWidget (self .done_metric )
        self .metrics_layout .addWidget (self .runs_metric )
        content_layout .addLayout (self .metrics_layout )

        projects_header =QHBoxLayout ()
        projects_title =QLabel ("Projects")
        projects_title .setObjectName ("SectionTitle")
        projects_hint =QLabel ("Open a project to view video, charts and report")
        projects_hint .setObjectName ("SectionHint")
        projects_header .addWidget (projects_title )
        projects_header .addStretch (1 )
        projects_header .addWidget (projects_hint )
        content_layout .addLayout (projects_header )

        self .projects_grid =ResponsiveGrid (min_column_width =330 ,spacing =14 )
        content_layout .addWidget (self .projects_grid )

        runs_title =QLabel ("Recent Runs")
        runs_title .setObjectName ("SectionTitle")
        content_layout .addWidget (runs_title )

        self .runs_table =QTableWidget (0 ,5 )
        self .runs_table .setObjectName ("RunsTable")
        self .runs_table .setHorizontalHeaderLabels (["Project","Status","Created","Updated","Provider"])
        self .runs_table .verticalHeader ().setVisible (False )
        self .runs_table .setAlternatingRowColors (False )
        self .runs_table .setSelectionBehavior (QTableWidget .SelectionBehavior .SelectRows )
        self .runs_table .setSelectionMode (QTableWidget .SelectionMode .NoSelection )
        self .runs_table .setEditTriggers (QTableWidget .EditTrigger .NoEditTriggers )
        self .runs_table .setMinimumHeight (240 )
        header_view =self .runs_table .horizontalHeader ()
        header_view .setSectionResizeMode (0 ,QHeaderView .ResizeMode .Stretch )
        header_view .setSectionResizeMode (1 ,QHeaderView .ResizeMode .ResizeToContents )
        header_view .setSectionResizeMode (2 ,QHeaderView .ResizeMode .ResizeToContents )
        header_view .setSectionResizeMode (3 ,QHeaderView .ResizeMode .ResizeToContents )
        header_view .setSectionResizeMode (4 ,QHeaderView .ResizeMode .ResizeToContents )
        content_layout .addWidget (self .runs_table )

        content_layout .addStretch (1 )
        self .content_scroll .setWidget (content )
        main_layout .addWidget (self .content_scroll ,1 )

        root .addWidget (self .main_panel ,1 )

    def _build_sidebar (self )->QWidget :
        sidebar =QFrame ()
        sidebar .setObjectName ("Sidebar")
        sidebar .setFixedWidth (220 )
        layout =QVBoxLayout (sidebar )
        layout .setContentsMargins (12 ,14 ,12 ,14 )
        layout .setSpacing (10 )

        self .brand_label =QLabel ("EmotionVision")
        self .brand_label .setStyleSheet ("font-size: 24px; font-weight: 700; color: #2b3f71;")
        layout .addWidget (self .brand_label )

        self .sidebar_buttons =[]
        self ._nav_buttons_by_key :dict [str ,QPushButton ]={}
        nav_data :list [tuple [str ,str ,str ,object ]]=[
        ("projects","Projects","PR",self ._on_open_projects_clicked ),
        ("profile","Profile","PF",self .open_profile_requested .emit ),
        ("admin","Admin","AD",self .open_admin_requested .emit ),
        ]
        for key ,full_text ,compact_text ,handler in nav_data :
            button =QPushButton (full_text )
            button .setObjectName ("SidebarNavButton")
            button .setProperty ("active","false")
            button .setProperty ("fullText",full_text )
            button .setProperty ("compactText",compact_text )
            button .setProperty ("viewKey",key )
            button .clicked .connect (handler )
            self .sidebar_buttons .append (button )
            self ._nav_buttons_by_key [key ]=button 
            layout .addWidget (button )

        layout .addStretch (1 )

        self .sidebar_user_label =QLabel ("User")
        self .sidebar_user_label .setStyleSheet ("font-weight: 700; color: #243760;")
        self .sidebar_role_label =QLabel ("-")
        self .sidebar_role_label .setObjectName ("SectionHint")
        self .sidebar_logout_button =QPushButton ("Logout")
        self .sidebar_logout_button .setObjectName ("SecondaryButton")
        self .sidebar_logout_button .clicked .connect (self .logout_requested .emit )

        layout .addWidget (self .sidebar_user_label )
        layout .addWidget (self .sidebar_role_label )
        layout .addWidget (self .sidebar_logout_button )
        return sidebar 

    def _build_header (self )->QWidget :
        frame =QFrame ()
        frame .setObjectName ("HeaderBar")
        layout =QVBoxLayout (frame )
        layout .setContentsMargins (14 ,12 ,14 ,12 )
        layout .setSpacing (10 )

        self .header_layout =QBoxLayout (QBoxLayout .Direction .LeftToRight )
        self .header_layout .setSpacing (12 )

        self .greeting_label =QLabel ("Welcome")
        self .greeting_label .setObjectName ("GreetingLabel")
        self .greeting_label .setWordWrap (True )
        self .header_layout .addWidget (self .greeting_label ,1 )

        actions =QWidget ()
        self .actions_layout =QHBoxLayout (actions )
        self .actions_layout .setContentsMargins (0 ,0 ,0 ,0 )
        self .actions_layout .setSpacing (8 )

        self .search_input =QLineEdit ()
        self .search_input .setPlaceholderText ("Search by title or description")
        self .search_input .textChanged .connect (self ._apply_filter )
        self .search_input .setMinimumWidth (250 )

        self .models_label =QLabel ("Models: -")
        self .models_label .setObjectName ("SectionHint")

        self .refresh_button =QPushButton ("Refresh")
        self .refresh_button .setObjectName ("SecondaryButton")
        self .refresh_button .clicked .connect (self .refresh_requested .emit )

        self .create_button =QPushButton ("Create Project")
        self .create_button .setObjectName ("PrimaryButton")
        self .create_button .clicked .connect (self ._open_create_dialog )

        self .actions_layout .addWidget (self .search_input )
        self .actions_layout .addWidget (self .models_label )
        self .actions_layout .addWidget (self .refresh_button )
        self .actions_layout .addWidget (self .create_button )

        self .header_layout .addWidget (actions ,0 )
        layout .addLayout (self .header_layout )
        return frame 

    def set_models (self ,models :list [str ])->None :
        self ._models =[item .strip ()for item in models if item .strip ()]
        if self ._models :
            self .models_label .setText (f"Models: {len (self ._models )}")
        else :
            self .models_label .setText ("Models: unavailable")

    def set_detectors (self ,detectors :list [str ])->None :
        self ._detectors =[item .strip ()for item in detectors if item .strip ()]

    def set_audio_providers (self ,providers :list [AudioProvider ])->None :
        self ._audio_providers =[item for item in providers if item .code ]

    def set_camera_output_dir (self ,path :Path )->None :
        self ._camera_output_dir =path 

    def _open_create_dialog (self )->None :
        if not self ._models :
            self .set_status_message (
            "Models list is unavailable. You can still create an audio-only project.",
            is_error =True ,
            )

        dialog =CreateProjectDialog (
        models =self ._models ,
        detectors =self ._detectors ,
        audio_providers =self ._audio_providers ,
        camera_output_dir =self ._camera_output_dir ,
        parent =self ,
        )
        if dialog .exec ()==QDialog .DialogCode .Accepted :
            payload =dialog .payload ()
            self .create_project_requested .emit (
            payload .title ,
            payload .description ,
            payload .video_path ,
            payload .start_processing ,
            payload .model_name ,
            payload .detector_name ,
            payload .processing_mode ,
            payload .audio_provider ,
            )

    def set_user (self ,user :UserProfile )->None :
        self .greeting_label .setText (f"Welcome, {user .ui_name }")
        self .sidebar_user_label .setText (user .ui_name )
        self .sidebar_role_label .setText (user .role )
        self .set_admin_mode (user .role =="admin")

    def set_loading (self ,loading :bool ,message :str |None =None )->None :
        self .refresh_button .setDisabled (loading )
        self .create_button .setDisabled (loading )
        self .sidebar_logout_button .setDisabled (loading )
        if loading and message :
            self .set_status_message (message ,is_error =False )

    def set_status_message (self ,message :str ,*,is_error :bool )->None :
        if not message :
            self .status_message .hide ()
            self .status_message .clear ()
            return 

        self .status_message .setStyleSheet ("color: #c63f57;"if is_error else "color: #4d5a86;")
        self .status_message .setText (message )
        self .status_message .show ()

    def set_admin_mode (self ,is_admin :bool )->None :
        self ._is_admin =is_admin 
        admin_button =self ._nav_buttons_by_key .get ("admin")
        if admin_button is not None :
            admin_button .setVisible (is_admin )

    def set_active_nav (self ,view_key :str )->None :
        for key ,button in self ._nav_buttons_by_key .items ():
            button .setProperty ("active","true"if key ==view_key else "false")
            button .style ().unpolish (button )
            button .style ().polish (button )

    def _on_open_projects_clicked (self )->None :
        self .set_active_nav ("projects")
    def set_dashboard_data (
    self ,
    *,
    projects :list [Project ],
    runs :list [tuple [Project ,ProcessingRun |None ]],
    )->None :
        self ._all_projects =list (projects )
        self ._runs_by_project ={str (project .id ):run for project ,run in runs }
        self ._refresh_metrics ()
        self ._apply_filter ()

    def _refresh_metrics (self )->None :
        total =len (self ._all_projects )
        active =sum (1 for project in self ._all_projects if project .status in {"draft","in_progress"})
        done =sum (1 for project in self ._all_projects if project .status =="done")
        with_runs =sum (1 for project in self ._all_projects if self ._runs_by_project .get (str (project .id ))is not None )

        self .total_metric .set_value (str (total ))
        self .active_metric .set_value (str (active ))
        self .done_metric .set_value (str (done ))
        self .runs_metric .set_value (str (with_runs ))

    def _apply_filter (self ,*_ :object )->None :
        query =self .search_input .text ().strip ().lower ()
        if not query :
            projects =list (self ._all_projects )
        else :
            projects =[
            project 
            for project in self ._all_projects 
            if query in project .title .lower ()or query in (project .description or "").lower ()
            ]

        self ._render_project_cards (projects )
        self ._render_runs_table (projects )

    def _render_project_cards (self ,projects :list [Project ])->None :
        items :list [QWidget ]=[]
        if not projects :
            empty =QFrame ()
            empty .setObjectName ("EmptyState")
            empty_layout =QVBoxLayout (empty )
            empty_layout .setContentsMargins (24 ,24 ,24 ,24 )
            empty_layout .setSpacing (6 )
            title =QLabel ("No projects found")
            title .setObjectName ("ProjectTitle")
            hint =QLabel ("Change the filter or create a new project.")
            hint .setObjectName ("SectionHint")
            empty_layout .addWidget (title )
            empty_layout .addWidget (hint )
            empty_layout .addStretch (1 )
            items .append (empty )
        else :
            for project in projects :
                card =ProjectCard (project )
                card .open_project_requested .connect (self .open_project_requested .emit )
                items .append (card )

        self .projects_grid .set_items (items )

    def _render_runs_table (self ,projects :list [Project ])->None :
        rows :list [tuple [Project ,ProcessingRun |None ]]=[]
        for project in projects :
            rows .append ((project ,self ._runs_by_project .get (str (project .id ))))

        def sort_key (item :tuple [Project ,ProcessingRun |None ])->float :
            run =item [1 ]
            dt =run .created_at if run else item [0 ].updated_at 
            return dt .timestamp ()if dt else 0.0 

        rows .sort (key =sort_key ,reverse =True )
        rows =rows [:20 ]

        self .runs_table .setRowCount (len (rows ))
        for row_index ,(project ,run )in enumerate (rows ):
            status_value =run .status if run else "-"
            status_text =run_status_label (status_value )if run else "No runs"
            status_item =QTableWidgetItem (status_text )
            if run :
                status_color =self ._status_color (run .status )
                status_item .setForeground (QBrush (status_color ))

            self .runs_table .setItem (row_index ,0 ,QTableWidgetItem (project .title ))
            self .runs_table .setItem (row_index ,1 ,status_item )
            self .runs_table .setItem (row_index ,2 ,QTableWidgetItem (format_datetime (run .created_at if run else None )))
            self .runs_table .setItem (
            row_index ,
            3 ,
            QTableWidgetItem (format_datetime (run .updated_at if run else project .updated_at )),
            )
            self .runs_table .setItem (row_index ,4 ,QTableWidgetItem (run .provider if run else "-"))

    def _status_color (self ,status :str )->QColor :
        mapping ={
        "scheduled":QColor ("#2f5cb1"),
        "pending":QColor ("#6f50b5"),
        "running":QColor ("#996f00"),
        "completed":QColor ("#1f7c4a"),
        "failed":QColor ("#bb334a"),
        "cancelled":QColor ("#566084"),
        }
        return mapping .get (status ,QColor ("#4d5a84"))

    def _apply_responsive_mode (self )->None :
        width =self .width ()
        compact_sidebar =width <1240 
        narrow =width <980 

        if compact_sidebar :
            self .sidebar .setFixedWidth (82 )
            self .brand_label .hide ()
            self .sidebar_user_label .hide ()
            self .sidebar_role_label .hide ()
            for button in self .sidebar_buttons :
                button .setText (str (button .property ("compactText")))
                button .setToolTip (str (button .property ("fullText")))
        else :
            self .sidebar .setFixedWidth (220 )
            self .brand_label .show ()
            self .sidebar_user_label .show ()
            self .sidebar_role_label .show ()
            for button in self .sidebar_buttons :
                button .setText (str (button .property ("fullText")))
                button .setToolTip ("")

        if narrow :
            self .header_layout .setDirection (QBoxLayout .Direction .TopToBottom )
            self .metrics_layout .setDirection (QBoxLayout .Direction .TopToBottom )
            self .projects_grid .set_min_column_width (240 )
        else :
            self .header_layout .setDirection (QBoxLayout .Direction .LeftToRight )
            self .metrics_layout .setDirection (QBoxLayout .Direction .LeftToRight )
            if width <1350 :
                self .projects_grid .set_min_column_width (290 )
            else :
                self .projects_grid .set_min_column_width (330 )

    def resizeEvent (self ,event )->None :# type: ignore[override]
        super ().resizeEvent (event )
        self ._apply_responsive_mode ()

