// Command ingest fetches GitHub releases for the opportunities the finder ranked
// and writes them as normalized records for the page compiler.
//
//	go run . -opportunities ../../opportunity-finder/output/opportunities-<ts>.json -top 50 -out records.json
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"
)

// Release is the subset of GitHub's release object we use. Nested objects
// (author, assets) are left out, so decoding never trips on their shape.
type Release struct {
	TagName     string    `json:"tag_name"`
	Name        string    `json:"name"`
	Body        string    `json:"body"`
	HTMLURL     string    `json:"html_url"`
	Draft       bool      `json:"draft"`
	Prerelease  bool      `json:"prerelease"`
	PublishedAt time.Time `json:"published_at"`
}

// Record is what the compiler consumes: one page per record.
type Record struct {
	Project       string    `json:"project"`
	Repo          string    `json:"repo"`
	Tag           string    `json:"tag"`
	Query         string    `json:"query"`
	Opportunity   float64   `json:"opportunity"`
	ReleaseURL    string    `json:"release_url"`
	PublishedAt   time.Time `json:"published_at"`
	PreviousTag   string    `json:"previous_tag"`
	Body          string    `json:"body"`
	BreakingLines []string  `json:"breaking_lines"`
}

type opportunity struct {
	Project     string  `json:"project"`
	Release     string  `json:"release"`
	Query       string  `json:"query"`
	Opportunity float64 `json:"opportunity"`
	ReleaseURL  string  `json:"release_url"`
}

var breakingRE = regexp.MustCompile(`(?i)breaking|removed|deprecat|no longer|migrat|renamed|drop(ped)? support|minimum .*version`)

var client = &http.Client{Timeout: 20 * time.Second}

func fetchReleases(repo string) ([]Release, error) {
	req, _ := http.NewRequest("GET", fmt.Sprintf("https://api.github.com/repos/%s/releases?per_page=30", repo), nil)
	req.Header.Set("Accept", "application/vnd.github+json")
	if t := os.Getenv("GITHUB_TOKEN"); t != "" {
		req.Header.Set("Authorization", "Bearer "+t)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%s: http status %d", repo, resp.StatusCode)
	}
	var rels []Release
	if err := json.NewDecoder(resp.Body).Decode(&rels); err != nil {
		return nil, fmt.Errorf("%s: decode: %w", repo, err)
	}
	return rels, nil
}

func breakingLines(body string) []string {
	var out []string
	for _, l := range strings.Split(body, "\n") {
		l = strings.TrimSpace(strings.TrimLeft(strings.TrimSpace(l), "-*"))
		if l != "" && breakingRE.MatchString(l) {
			out = append(out, l)
		}
	}
	return out
}

// buildRecord finds the opportunity's release in the repo's release list and
// pairs it with the previous stable release, so pages can say "from X to Y".
func buildRecord(op opportunity, repo string, rels []Release) (Record, bool) {
	for i, r := range rels {
		if r.TagName != op.Release || r.Draft {
			continue
		}
		prev := ""
		for _, p := range rels[i+1:] {
			if !p.Draft && !p.Prerelease {
				prev = p.TagName
				break
			}
		}
		return Record{
			Project: op.Project, Repo: repo, Tag: r.TagName, Query: op.Query,
			Opportunity: op.Opportunity, ReleaseURL: r.HTMLURL, PublishedAt: r.PublishedAt,
			PreviousTag: prev, Body: r.Body, BreakingLines: breakingLines(r.Body),
		}, true
	}
	return Record{}, false
}

func main() {
	opsPath := flag.String("opportunities", "", "finder output JSON")
	watchPath := flag.String("watchlist", "../../opportunity-finder/watchlist.json", "watchlist JSON (project name -> repo)")
	top := flag.Int("top", 50, "how many top opportunities to ingest")
	out := flag.String("out", "records.json", "output file")
	flag.Parse()
	if *opsPath == "" {
		log.Fatal("-opportunities is required")
	}

	var ops struct {
		Opportunities []opportunity `json:"opportunities"`
	}
	var wl struct {
		Projects []struct{ Name, Repo string } `json:"projects"`
	}
	mustReadJSON(*opsPath, &ops)
	mustReadJSON(*watchPath, &wl)
	repoOf := map[string]string{}
	for _, p := range wl.Projects {
		repoOf[p.Name] = p.Repo
	}

	if len(ops.Opportunities) > *top {
		ops.Opportunities = ops.Opportunities[:*top]
	}
	cache := map[string][]Release{}
	var records []Record
	for _, op := range ops.Opportunities {
		repo := repoOf[op.Project]
		if repo == "" {
			log.Printf("skip %s: not in watchlist", op.Project)
			continue
		}
		rels, ok := cache[repo]
		if !ok {
			var err error
			if rels, err = fetchReleases(repo); err != nil {
				log.Printf("skip %s: %v", repo, err)
				continue
			}
			cache[repo] = rels
		}
		if rec, ok := buildRecord(op, repo, rels); ok {
			records = append(records, rec)
		}
	}

	f, err := os.Create(*out)
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	if err := enc.Encode(records); err != nil {
		log.Fatal(err)
	}
	fmt.Printf("wrote %d records to %s\n", len(records), *out)
}

func mustReadJSON(path string, v any) {
	b, err := os.ReadFile(path)
	if err != nil {
		log.Fatal(err)
	}
	if err := json.Unmarshal(b, v); err != nil {
		log.Fatalf("%s: %v", path, err)
	}
}
