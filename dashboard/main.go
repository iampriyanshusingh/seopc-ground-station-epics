package main

import (
	"database/sql"
	"fmt"
	"log"
	"math"
	"strings"
	"time"

	"github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	_ "github.com/lib/pq"
)

// === Config & Constants ===
const (
	pgConnStr = "postgres://admin:password123@localhost:5432/seopc_metadata?sslmode=disable"
)

// === Styles ===
var (
	subtle    = lipgloss.AdaptiveColor{Light: "#D9DCCF", Dark: "#383838"}
	highlight = lipgloss.AdaptiveColor{Light: "#874BFD", Dark: "#7D56F4"}
	special   = lipgloss.AdaptiveColor{Light: "#43BF6D", Dark: "#73F59F"}
	danger    = lipgloss.AdaptiveColor{Light: "#F25D94", Dark: "#F55385"}

	titleStyle = lipgloss.NewStyle().
		MarginLeft(1).
		MarginRight(5).
		Padding(0, 1).
		Italic(true).
		Foreground(lipgloss.Color("#FFF7DB")).
		SetString("PROJECT ARGUS")

	statusActive = lipgloss.NewStyle().
		Foreground(special).
		SetString("ORBITAL LINK ACTIVE")

	statusOffline = lipgloss.NewStyle().
		Foreground(danger).
		SetString("ORBITAL LINK SEVERED")

	boxStyle = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(highlight).
		Padding(1, 2)
		
	introStyle = lipgloss.NewStyle().
		Foreground(lipgloss.Color("63")). // Blueish
		Align(lipgloss.Center)
)

// === Model ===
type State int

const (
	StateIntro State = iota
	StateDashboard
)

type model struct {
	state       State
	db          *sql.DB
	width       int
	height      int
	processed   int
	lastFile    string
	latency     int
	detections  string
	err         error
	introTicks  int
}

type tickMsg time.Time

func checkDb(db *sql.DB) tea.Cmd {
	return func() tea.Msg {
		var count int
		var lastFile string
		var latency int
		var detections sql.NullString // Handle potential nulls

		// Get count
		db.QueryRow("SELECT COUNT(*) FROM processing_logs").Scan(&count)

		// Get latest
		err := db.QueryRow("SELECT filename, latency_ms, result::text FROM processing_logs ORDER BY processed_at DESC LIMIT 1").Scan(&lastFile, &latency, &detections)
		
		dStr := "Scanning..."
		if err == nil {
			if detections.Valid { dStr = detections.String[0:int(math.Min(float64(len(detections.String)), 50))] + "..." }
		} else {
			lastFile = "Waiting for Satellite..."
		}
		
		return dbStatsMsg{count, lastFile, latency, dStr}
	}
}

type dbStatsMsg struct {
	processed  int
	lastFile   string
	latency    int
	detections string
}

func initialModel() model {
	db, err := sql.Open("postgres", pgConnStr)
	if err != nil {
		log.Fatal(err)
	}
	return model{
		state: StateIntro,
		db:    db,
	}
}

func (m model) Init() tea.Cmd {
	return tickCmd()
}

func tickCmd() tea.Cmd {
	return tea.Tick(time.Millisecond*100, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

func (m model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		if msg.String() == "q" || msg.String() == "ctrl+c" {
			return m, tea.Quit
		}
	
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height

	case tickMsg:
		if m.state == StateIntro {
			m.introTicks++
			if m.introTicks > 50 { // 5 seconds intro
				m.state = StateDashboard
			}
			return m, tickCmd()
		}
		return m, tea.Batch(checkDb(m.db), tickCmd())

	case dbStatsMsg:
		m.processed = msg.processed
		m.lastFile = msg.lastFile
		m.latency = msg.latency
		m.detections = msg.detections
	}
	return m, nil
}

func (m model) View() string {
	if m.state == StateIntro {
		return m.introView()
	}
	return m.dashboardView()
}

func (m model) introView() string {
	// Simple ASCII animation of a growing blackhole
	// Frame logic
	frames := []string{
		"   .   ",
		"  (.)  ",
		" ((.)) ",
		"(((.)))", 
		"  (@)  ",
	}
	
	idx := (m.introTicks / 5) % len(frames)
	art := frames[idx]
	
	// Complex Blackhole Ascii
	bh := `
         .   
       .  *  .
     *   .   *
    .  ( O )  .
     *   .   *
       .   .
         .
	`
	if m.introTicks > 20 {
		bh = `
      :   :   :
    .   .   .   .
   .  (  @  )  .
    .   '   '   .
      :   :   :
		`
	}
	
	title := "INITIALIZING PROJEKT ARGUS..."
	if m.introTicks > 35 {
		title = "ESTABLISHING ORBITAL UPLINK :: SECURITY LEVEL 9"
	}
	if m.introTicks > 45 {
		title = "ACCESS GRANTED"
	}

	// Center content
	return fmt.Sprintf("\n\n\n\n%s\n\n%s\n\n%s", 
		introStyle.Render(bh),
		introStyle.Render(art),
		introStyle.Render(title),
	)
}

func (m model) dashboardView() string {
	status := statusActive.String()
	if m.err != nil {
		status = statusOffline.String()
	}

	// Calculate Throughput (fake for visual, or simple avg)
	tput := 0.0
	if m.processed > 0 {
		tput = float64(m.processed * 60) // Just a placeholder formula
	}

	// Analytics Box
	statsContent := fmt.Sprintf(
		"TOTAL SCENES:     %d\n\nAVG LATENCY:      %d ms\n\nEST. THROUGHPUT:  %.1f img/hr",
		m.processed,
		m.latency,
		tput, 
	)
	
	// Telemetry Box
	telemetryContent := fmt.Sprintf(
		"LATEST FILE:  %s\n\nLATENCY:      %d ms\n\nCV DETECT:    %s",
		m.lastFile,
		m.latency,
		strings.ReplaceAll(m.detections, "\"", ""),
	)

	leftBox := boxStyle.Width(45).Height(10).Render(statsContent)
	rightBox := boxStyle.Width(60).Height(10).Render(telemetryContent)

	header := titleStyle.Render()
	
	ui := lipgloss.JoinVertical(lipgloss.Left,
		header,
		fmt.Sprintf("\nSTATUS: %s", status),
		"\n",
		lipgloss.JoinHorizontal(lipgloss.Top, leftBox, rightBox),
		"\n\n[Q] TERMINATE UPLINK",
	)

	return ui
}

func main() {
	p := tea.NewProgram(initialModel(), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		log.Fatal(err)
	}
}
