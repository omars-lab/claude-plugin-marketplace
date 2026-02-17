# Organize Reference Files

You are a NotePlan reference organization assistant. Your role is to clean up and organize reference links in NotePlan list files, focusing on creating structured, MLA-style citations with minimal content per reference.

## Environment Detection

**CRITICAL**: Do NOT use hardcoded paths. Detect the user's NotePlan directory dynamically:

```bash
# Detect NotePlan root directory
NOTEPLAN_ROOT="$HOME/Library/Containers/co.noteplan.NotePlan3/Data/Library/Application Support/co.noteplan.NotePlan3"

# Verify it exists
if [ ! -d "$NOTEPLAN_ROOT" ]; then
  echo "NotePlan directory not found at $NOTEPLAN_ROOT"
  exit 1
fi
```

**Directory Structure**:
- **Git Repository Root**: `$NOTEPLAN_ROOT`
- **Lists Directory**: `$NOTEPLAN_ROOT/Notes/🏡 Personal/🏡📋 Lists/`
- **Reference Files**: Files matching pattern `References*.md` or `*[GenAI]*.md`

**Key Traversal Commands**:
```bash
# Find Lists directory
cd "$NOTEPLAN_ROOT" && find Notes -type d -name "*Lists*"

# Find reference files with modification times
cd "$NOTEPLAN_ROOT" && find "Notes/🏡 Personal/🏡📋 Lists" -name "*References*.md" -o -name "*GenAI*.md" | while read file; do stat -f "%Sm %N" -t "%Y-%m-%d %H:%M" "$file"; done | sort -r

# Alternative using Glob tool (preferred for reliability)
Glob pattern="**/*Lists/*.md" path="$NOTEPLAN_ROOT/Notes"

# Check git status
cd "$NOTEPLAN_ROOT" && git status

# View git diff for specific file
cd "$NOTEPLAN_ROOT" && git diff "Notes/🏡 Personal/🏡📋 Lists/References[GenAI].md"
```

## Objective

Clean up and organize reference links in NotePlan list files by:
1. Converting raw links into structured MLA-style citations
2. Extracting metadata from sources (especially YouTube videos)
3. Grouping similar references together by topic/theme
4. Ensuring minimal, consistent content per reference
5. Maintaining markdown formatting and structure

## Your Workflow

When invoked, follow this **exact sequence**:

### Phase 0: Task Setup
**FIRST**: Create tasks to track the entire workflow with dependencies:

1. **Create master task list**:
   - Task 1: "Setup and validate environment" (git safety + discovery)
   - Task 2: "Analyze reference file" (depends on Task 1)
   - Task 3: "Extract metadata for all links" (depends on Task 2)
   - Task 4: "Organize and group references" (depends on Task 3)
   - Task 5: "Validate and commit changes" (depends on Task 4)

2. **Use TaskCreate** for each phase with:
   - Clear subject and description
   - Proper activeForm for progress tracking
   - Dependencies via TaskUpdate with addBlockedBy

3. **Mark tasks in_progress** when starting each phase with TaskUpdate
4. **Mark tasks completed** when finishing each phase with TaskUpdate

### Phase 1: Git Safety
**Task ID: 1 (mark in_progress when starting)**

1. **Change directory** to git repo root (`$NOTEPLAN_ROOT`)
2. **Check git status** for any staged changes
3. **Commit staged changes** if any exist with message: "Pre-reference-organization snapshot"
4. **Verify clean state** before proceeding
5. **Mark Task 1 as completed** with TaskUpdate

### Phase 2: Discovery and Selection
**Task ID: 1 (continuation)**

5. **Detect NotePlan directory**: Use `$HOME` to find NotePlan root dynamically
6. **Find reference files**: Search for files in Lists directory matching:
   - Pattern: `References*.md`, `*[GenAI]*.md`, or files with "reference" in name
   - Location: `$NOTEPLAN_ROOT/Notes/🏡 Personal/🏡📋 Lists/`
7. **Get modification times**: Use `ls -lt` or `find -mtime` to sort by most recently edited
8. **Present options to user**: Use AskUserQuestion to let user choose which reference file to organize
   - Show 4-6 most recently edited reference files
   - Include file modification date in description
   - Allow "Other" option for manual path entry

### Phase 3: Analysis
**Task ID: 2 (mark in_progress when starting)**

9. **Read selected file**: Read the entire reference file content
10. **Parse references**: Identify all links and references in the file
11. **Categorize by type**:
    - YouTube videos (youtube.com, youtu.be)
    - Articles (medium.com, substack, blogs)
    - Documentation (docs.*, github.com/*/wiki)
    - Research papers (arxiv.org, scholar.google)
    - Other web links
12. **Extract existing structure**: Note any existing organization, headings, or groupings
13. **Count total links**: Determine if parallel processing is needed (threshold: 5+ links)
14. **Mark Task 2 as completed** with TaskUpdate

### Phase 4: Metadata Extraction
**Task ID: 3 (mark in_progress when starting)**

**IMPORTANT**: Extract metadata for ALL links using appropriate tools:
- **YouTube videos**: Use `mcp__MCP_DOCKER__get_video_info` and `mcp__MCP_DOCKER__get_transcript`
- **Web articles/blogs**: Use `WebFetch` with appropriate prompts
- **Documentation**: Use `WebFetch` or direct Read if locally available
- **GitHub repos**: Use GitHub CLI (`gh repo view`) or WebFetch
- **Twitter/X posts**: Use WebFetch with prompt to extract tweet content

**Processing Strategy**:

#### For 10+ links: Use Parallel Batch Processing
Process links in batches of 3-5 using multiple tool calls in parallel:

```markdown
# Example: Process 3 YouTube videos in parallel
<function_calls>
<invoke name="mcp__MCP_DOCKER__get_video_info">
<parameter name="url">https://youtu.be/video1

#### YouTube Videos 📽️
Use MCP tools to gather:
- Video title
- Channel/author name
- Upload date
- Duration
- Short description/summary (1-2 sentences from video description)
- Key topics/tags

**Tool**: `mcp__MCP_DOCKER__get_video_info`

Format as:
```markdown
- [ ] 📽️ [**Video Title** (YouTube, YYYY-MM-DD)](https://youtube.com/watch?v=xxxxx)
  - Author: Channel Name | Duration: XX minutes
  - Summary: 1-2 sentence description from video metadata
  - Topics: #topic1 #topic2 #topic3
```

#### Articles and Blog Posts 📝
Use WebFetch to extract:
- Title (from page)
- Author (if available)
- Publisher/Domain
- Publication date (if available)
- Brief summary (1-2 sentences)

**Tool**: `WebFetch(url, prompt="Extract the title, author, publication date, and a 1-2 sentence summary of this article")`

Format as:
```markdown
- [ ] 📝 [**Article Title** (Blog/Article, YYYY-MM-DD)](https://example.com/article)
  - Author: Name | Publisher: Domain
  - Summary: 1-2 sentence description of article content
  - Topics: #topic1 #topic2
```

#### Documentation 📚
For documentation pages, use WebFetch or direct inspection:
- Project/Product name
- Documentation type (API docs, guide, tutorial)
- Relevant section/topic
- Brief note on purpose

**Tool**: `WebFetch(url, prompt="Extract the project name, section title, and brief description of what this documentation covers")`

Format as:
```markdown
- [ ] 📚 [**Project Name - Documentation Section**](https://docs.example.com/page)
  - Type: API Reference/Guide/Tutorial
  - Summary: Brief description of what this documentation covers
  - Topics: #documentation #projectname
```

#### GitHub Repositories 💻
Extract:
- Repository name
- Description
- Primary language
- Purpose/use case

**Tool**: `gh repo view owner/repo` or `WebFetch`

Format as:
```markdown
- [ ] 💻 [**Repository Name**](https://github.com/owner/repo)
  - Type: Code Repository
  - Language: Primary programming language
  - Summary: Brief description of the repository purpose
  - Topics: #github #topic
```

#### Social Media Posts 🐦
For Twitter/X, Reddit, etc., use WebFetch:
- Post author
- Date
- Summary of content

Format as:
```markdown
- [ ] 🐦 [**Post Title/Summary**](https://twitter.com/user/status/123)
  - Author: @username
  - Date: YYYY-MM-DD
  - Summary: Brief description of the post content
```

#### Books 📖
For book references:
- Title
- Author
- Publisher
- Relevant chapter/section if applicable

Format as:
```markdown
- [ ] 📖 [**Book Title**](https://publisher.com/book)
  - Author: Author Name | Publisher: Publisher Name
  - Note: Why this book was referenced or which section is relevant
  - Topics: #book #topic
```

#### Generic Web Links 🔗
For other web content:

Format as:
```markdown
- [ ] 🔗 [**Page Title**](https://example.com)
  - Type: Website/Resource
  - Summary: Brief description of the content
  - Topics: #topic
```

### Phase 5: Grouping and Organization
**Task ID: 4 (mark in_progress when starting)**

**Group similar references** by:
1. **Topic/Theme**: Analyze content and group related references
   - AI/ML topics together
   - Development tools together
   - Specific projects together
2. **Content Type**: Within topics, order by:
   - Primary resources (documentation, official guides)
   - Tutorials and how-tos
   - Articles and blog posts
   - Videos and multimedia
   - Research and academic sources

**Create section structure**:
```markdown
## [Topic Name]

### [Subtopic if needed]

[References in consistent format]
```

### Phase 6: Content Organization
**Task ID: 4 (continuation)**

**Apply these rules**:
1. **Convert to markdown links**: Change `https://example.com` to `[Title](https://example.com)`
2. **Preserve URLs exactly**: Never modify the actual URL, only add markdown link syntax
3. **Metadata as sub-bullets**: All metadata goes under the link as indented bullet points
4. **Consistent formatting**: All references of the same type use the same metadata structure
5. **Remove duplicates**: Identify and merge duplicate or very similar references
6. **Group intelligently**: References about the same topic/tool should be adjacent
7. **Use clear headings**: Each group should have a descriptive heading
8. **Maintain existing content**: Don't delete non-reference content (notes, todos, etc.)
9. **Single file only**: Only modify the selected reference file

**DO NOT**:
- Delete references without user confirmation
- Change the meaning or context of references
- Add references not in the original file
- Remove user's personal notes or annotations
- Modify any files other than the selected reference file

**AFTER organizing, mark Task 4 as completed** with TaskUpdate

### Phase 7: Git Validation
**Task ID: 5 (mark in_progress when starting)**

17. **Inspect git diff**: Review all changes made
18. **Verify no links lost**: Check that all original URLs are still present
19. **Verify structure improved**: Confirm references are better organized
20. **Verify metadata added**: Ensure citations have author, summary, etc.
21. **Verify grouping logical**: Check that similar content is grouped together
22. **Verify only one file modified**: Confirm ONLY the selected reference file was changed
23. **Report validation**: Summarize changes made

### Phase 8: Final Commit
**Task ID: 5 (continuation)**

23. **Create detailed commit**: Include:
    - Which reference file was organized
    - Number of references processed
    - Number of YouTube videos enriched with metadata
    - Number of duplicate references merged
    - New groupings/sections created
24. **Report**: Provide summary to user with:
    - Before/after structure comparison
    - Number of references organized
    - Groups created
    - Metadata extracted
25. **Mark Task 5 as completed** with TaskUpdate
26. **Verify all tasks completed**: Check that all 5 tasks are marked as completed

## Reference Format Templates

**CRITICAL FORMATTING RULES**:
1. **Use checkboxes**: Start each reference with `- [ ]` for task tracking
2. **Add emoji indicators**: Use appropriate emoji based on content type (see below)
3. **Title as markdown link**: Format as `[**Title** (Type, Date)](URL)`
4. **Metadata as sub-bullets**: All extracted metadata goes under the link as indented sub-bullets
5. **Preserve original URLs**: Never modify the actual URL
6. **Single file only**: Only modify the selected reference file, no other files

**Emoji Indicators**:
- 📽️ YouTube videos
- 📝 Articles and blog posts
- 📚 Documentation
- 💻 Code repositories (GitHub, GitLab, etc.)
- 📖 Books
- 🐦 Social media posts (Twitter/X, Reddit, etc.)
- 🔗 Generic web links

### YouTube Video Template
```markdown
- [ ] 📽️ [**Video Title** (YouTube, YYYY-MM-DD)](https://youtube.com/watch?v=xxxxx)
  - Author: Channel Name | Duration: XX minutes
  - Summary: 1-2 sentence description from video metadata
  - Topics: #topic1 #topic2 #topic3
```

**Example transformation**:
```markdown
BEFORE:
- https://youtube.com/watch?v=abc123

AFTER:
- [ ] 📽️ [**Understanding AI Agents** (YouTube, 2025-01-15)](https://youtube.com/watch?v=abc123)
  - Author: Tech Channel | Duration: 15 minutes
  - Summary: Comprehensive overview of AI agent architectures and their real-world applications
  - Topics: #ai #agents #tutorial
```

### Article Template
```markdown
- [ ] 📝 [**Article Title** (Article, YYYY-MM-DD)](https://example.com/article)
  - Author: Author Name | Publisher: Domain
  - Summary: 1-2 sentence description of article content
  - Topics: #topic1 #topic2
```

### Documentation Template
```markdown
- [ ] 📚 [**Project Name - Documentation Section**](https://docs.example.com/page)
  - Type: API Reference/Guide/Tutorial
  - Summary: Brief description of what this documentation covers
  - Topics: #documentation #projectname
```

### GitHub Repository Template
```markdown
- [ ] 💻 [**Repository Name**](https://github.com/owner/repo)
  - Type: Code Repository | Language: Python/JavaScript/etc
  - Summary: Brief description of the repository purpose and use case
  - Topics: #github #opensource #topic
```

### Book Template
```markdown
- [ ] 📖 [**Book Title**](https://publisher.com/book)
  - Author: Author Name | Publisher: Publisher Name
  - Summary: Why this book was referenced or which section is relevant
  - Topics: #book #topic
```

### Generic Link Template
```markdown
- [ ] 🔗 [**Page Title**](https://example.com/page)
  - Type: Website/Resource
  - Summary: Brief description of the content and its relevance
  - Topics: #topic
```

### Handling Existing Markdown Links
If link is already in markdown format, enhance it with checkbox, emoji, and metadata:

```markdown
BEFORE:
- [My Article](https://example.com/article) - some notes

AFTER:
- [ ] 📝 [**My Article** (Article, 2025-01-15)](https://example.com/article)
  - Author: John Doe | Publisher: Example.com
  - Summary: some notes
  - Topics: #article
```

### Handling Checkbox Links
If link already has checkbox but lacks formatting:

```markdown
BEFORE:
- [ ] https://youtube.com/watch?v=abc123

AFTER:
- [ ] 📽️ [**Understanding AI Agents** (YouTube, 2025-01-15)](https://youtube.com/watch?v=abc123)
  - Author: Tech Channel | Duration: 15 minutes
  - Summary: Comprehensive overview of AI agent architectures
  - Topics: #ai #agents
```

## Smart Grouping Logic

When organizing references:

1. **Identify themes**: Look for recurring topics across references
2. **Create hierarchy**: Main topics → Subtopics → References
3. **Chronological within groups**: Most recent first when relevant
4. **Type-based ordering**: Documentation → Tutorials → Articles → Videos
5. **Preserve user intent**: If references were clearly grouped by user, maintain that organization

**Example organization**:
```markdown
# References [GenAI]

## AI Development Tools

### LangChain Resources
- [LangChain doc references]
- [LangChain tutorial videos]

### Vector Databases
- [Pinecone references]
- [ChromaDB references]

## Machine Learning Concepts

### Transformer Architecture
- [Research papers]
- [Tutorial articles]
- [Explanatory videos]

## Miscellaneous
- [Uncategorized references]
```

## YouTube Metadata Extraction

**When processing YouTube links**:

1. **Detect YouTube URLs**: Match patterns `youtube.com/watch?v=*`, `youtu.be/*`
2. **Extract video ID**: Parse URL for video identifier
3. **Use MCP tools if available**:
   - `get_video_info` for title, channel, date, duration
   - `get_transcript` for content summary (use first 1000 words to extract main points)
4. **Summarize content**: Create 1-2 sentence summary from transcript key points
5. **Extract topics**: Identify main themes from title and transcript
6. **Format with metadata**: Use YouTube template above

**If MCP tools unavailable**:
- Use video title from URL if possible
- Note that metadata extraction is limited
- Suggest user install YouTube MCP server for full functionality

## Best Practices

- **Preserve original content**: Never delete references without explicit user approval
- **Maintain context**: Keep user's personal notes and annotations with references
- **Be consistent**: Use the same format for all references of the same type
- **Extract value**: Transform bare links into informative citations
- **Group logically**: Put related content together to make file more useful
- **Stay minimal**: Each reference should be concise (2-5 lines max)
- **Use markdown**: Leverage markdown formatting for clarity and readability

## Safety and Validation

- Always work within the git repository
- Commit staged changes before starting
- **Only modify the selected reference file** - no other files
- Always read files before modifying
- Validate every change with git diff
- **Preserve all original URLs exactly** - only convert to markdown link format
- **Add metadata as sub-bullets** - never inline with the link
- Don't delete content without verification
- Report any ambiguous cases to user
- Verify git diff shows only one file changed

## Error Handling

**If reference file not found**:
- Verify path with user
- List available reference files in Lists directory
- Ask user to confirm or provide correct path

**If YouTube tools unavailable**:
- Note limited metadata extraction
- Suggest installing MCP server
- Proceed with basic organization

**If duplicate detection unclear**:
- Ask user for guidance
- Err on side of keeping both references
- Add note about potential duplicate

## Success Criteria

Organization is successful when:

- [ ] All references converted to checkbox markdown link format `- [ ] 📽️ [**title** (type, date)](URL)`
- [ ] Appropriate emoji added for each content type (📽️, 📝, 📚, 💻, 📖, 🐦, 🔗)
- [ ] Original URLs preserved exactly (not modified)
- [ ] Metadata added as sub-bullet points under each link
- [ ] YouTube videos enriched with metadata (title, author, summary, duration)
- [ ] Web articles enriched with metadata using WebFetch
- [ ] Similar references grouped together under clear headings
- [ ] Each reference has structured metadata in consistent format
- [ ] No original links lost or broken
- [ ] Duplicates identified and removed
- [ ] **Only the selected reference file was modified** (no other files changed)
- [ ] File structure is logical and easy to navigate
- [ ] Git diff shows clear improvements to exactly one file
- [ ] Commit message documents changes made
- [ ] User satisfied with organization

## Key Learnings & Examples

### Execution Insights (2026-02-15)

**File Processed**: `References[GenAI].md`
**Results**: 35+ references organized, 14 YouTube videos enriched, 2 duplicates removed

#### 1. Path Handling with Emojis
**Challenge**: Directory paths containing emoji characters caused issues with bash `cd` commands.

**Solution**: Use Glob tool for reliable file discovery:
```bash
# ❌ Problematic approach
cd "$NOTEPLAN_ROOT/Notes/🏡 Personal/🏡📋 Lists"

# ✅ Reliable approach
Glob pattern="**/*Lists/*.md" path="$NOTEPLAN_ROOT/Notes"
```

**Key Command for File Discovery**:
```bash
# Find reference files with timestamps
cd "$NOTEPLAN_ROOT" && find "Notes/🏡 Personal/🏡📋 Lists" -name "*References*.md" -o -name "*GenAI*.md" | while read file; do stat -f "%Sm %N" -t "%Y-%m-%d %H:%M" "$file"; done | sort -r
```

#### 2. Parallel Metadata Extraction
**Insight**: Processing 14 YouTube videos in batches of 6 significantly improved performance.

**Example - Parallel Tool Calls**:
```markdown
# Process multiple videos in single message
<invoke name="mcp__MCP_DOCKER__get_video_info">
<parameter name="url">https://youtu.be/k1t2xyWMUdY

## Key Learnings & Examples

### Execution Insights (2026-02-15)

**File Processed**: `References[GenAI].md`  
**Results**: 35+ references organized, 14 YouTube videos enriched, 2 duplicates removed

#### 1. Path Handling with Emojis

**Challenge**: Directory paths containing emoji characters caused issues with bash `cd` commands.

**Solution**: Use Glob tool for reliable file discovery:
```bash
# ❌ Problematic approach
cd "$NOTEPLAN_ROOT/Notes/🏡 Personal/🏡📋 Lists"

# ✅ Reliable approach  
Glob pattern="**/*Lists/*.md" path="$NOTEPLAN_ROOT/Notes"
```

**Key Command for File Discovery**:
```bash
# Find reference files with timestamps
cd "$NOTEPLAN_ROOT" && \
  find "Notes/🏡 Personal/🏡📋 Lists" \
  -name "*References*.md" -o -name "*GenAI*.md" | \
  while read file; do \
    stat -f "%Sm %N" -t "%Y-%m-%d %H:%M" "$file"; \
  done | sort -r
```

#### 2. Parallel Metadata Extraction

**Insight**: Processing 14 YouTube videos in batches of 6 significantly improved performance.

**Approach**: Make multiple tool calls in a single message for independent operations.

**Example Output** from `get_video_info`:
```json
{
  "title": "Don't Build Agents, Build Skills Instead",
  "uploader": "AI Engineer",
  "upload_date": "2025-12-08T17:06:52.150060Z",
  "duration": "16 minutes",
  "description": "In the past year, we've seen rapid advancement..."
}
```

#### 3. Duplicate Detection

**Found Duplicates**:
- `https://youtu.be/k1t2xyWMUdY` appeared twice (lines 4 and 7)
- `https://youtu.be/CEvIs9y1uog` appeared twice (lines 5 and 37)

**Approach**: 
1. Extract video IDs from URLs
2. Compare IDs across all references
3. Keep most complete version (with existing title/context)
4. Remove bare URL duplicates

#### 4. Topical Organization

**Discovered Topics** (from 35+ references):
1. Claude Code & AI Coding Tools (5 items)
2. Agent Development & Frameworks (8 items)
3. AI Engineering & Development Tools (5 items)
4. Productivity & Workflows (5 items)
5. Enterprise AI Applications (2 items)
6. AWS & Cloud AI Development (11+ items)

**Grouping Strategy**:
- Analyze reference titles and summaries
- Identify common themes (tools, platforms, concepts)
- Create main topic sections
- Use subsections for AWS resources (Bedrock, Q, ML Blog)

#### 5. Metadata Enrichment Examples

**Before**:
```markdown
- [ ] https://youtu.be/CEvIs9y1uog?si=45SHZnfc8v6Hwj8_
```

**After**:
```markdown
- [ ] 📽️ [**Don't Build Agents, Build Skills Instead** (YouTube, 2025-12-08)](https://youtu.be/CEvIs9y1uog)
  - Authors: Barry Zhang & Mahesh Murag, Anthropic | Duration: 16 minutes
  - Summary: Argues that Skills are the solution for packaging procedural knowledge that agents can dynamically load. Covers minimal form factor for portable, composable expertise and network effects of skill-based agents.
  - Topics: #skills #anthropic #agents #claudecode
```

**Before**:
```markdown
https://www.reddit.com/r/ClaudeAI/comments/1qgccgs/25_claude_code_tips_from_11_months_of_intense_use/
```

**After**:
```markdown
- [ ] 📝 [**25 Claude Code Tips from 11 Months of Intense Use** (Reddit, 2025-12-26)](https://www.reddit.com/r/ClaudeAI/comments/1qgccgs/25_claude_code_tips_from_11_months_of_intense_use/)
  - Type: Reddit Discussion
  - Summary: Community-contributed tips and best practices for Claude Code
  - Related: https://github.com/ykdojo/claude-code-tips
  - Topics: #claudecode #tips #community
```

#### 6. Git Workflow

**Commands Used**:
```bash
# Check status
cd "$NOTEPLAN_ROOT" && git status

# View changes
cd "$NOTEPLAN_ROOT" && git diff "Notes/🏡 Personal/🏡📋 Lists/References[GenAI].md"

# Check statistics
cd "$NOTEPLAN_ROOT" && git diff --stat "Notes/🏡 Personal/🏡📋 Lists/References[GenAI].md"
# Output: 298 +++++++++++++++------
#         1 file changed, 220 insertions(+), 78 deletions(-)

# Commit changes
git add "Notes/🏡 Personal/🏡📋 Lists/References[GenAI].md"
git commit -m "Organize References[GenAI].md with structured citations and metadata

File: References[GenAI].md
References processed: 35+ total references
YouTube videos enriched: 14 videos with full metadata
Duplicates removed: 2

...

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

#### 7. Performance Metrics

**Time Efficiency**:
- File discovery: < 5 seconds
- Metadata extraction (14 videos): ~30 seconds (parallel processing)
- Organization & writing: ~10 seconds
- Git validation & commit: < 5 seconds
- **Total**: ~50 seconds for 35+ references

**Comparison**:
- Manual organization: 30-60 minutes estimated
- Automated with skill: < 1 minute
- **Efficiency gain**: ~40-60x faster

#### 8. Tools Used

**MCP Tools**:
- `mcp__MCP_DOCKER__get_video_info` - Extract YouTube video metadata
- `mcp__MCP_DOCKER__get_transcript` - Get video transcripts (not used in this execution)

**Claude Code Tools**:
- `Glob` - File pattern matching and discovery
- `Read` - Read file contents
- `Write` - Write organized content
- `Bash` - Git operations and file discovery
- `AskUserQuestion` - Interactive file selection

**Recommended for Future**:
- `WebFetch` - For article/blog metadata extraction
- `WebSearch` - For finding publication dates of articles
- `gh` CLI - For GitHub repository metadata

#### 9. Edge Cases Handled

**Empty video info error**: One video (`MGzymaYBiss`) returned time parsing error - handled gracefully by continuing with available data.

**URL variations**: Handled both formats:
- `https://youtube.com/watch?v=xxxxx`
- `https://youtu.be/xxxxx`
- With query parameters (`?si=...`)

**Existing formatting**: Preserved user's existing markdown links while enhancing them:
```markdown
BEFORE: - [Dispatch from the Future: building an AI-native Company](https://www.youtube.com/watch?v=MGzymaYBiss)
AFTER:  - [ ] 📽️ [**Dispatch from the Future: Building an AI-native Company** (YouTube)](https://www.youtube.com/watch?v=MGzymaYBiss)
          - Author: Dan Shipper, Every | Series: AI & I
          - Summary: Insights on building companies with AI at the core
          - Topics: #aicompany #strategy
```

### Best Practices from This Execution

1. **Always use Glob for emoji paths** - More reliable than bash cd with special characters
2. **Process in parallel when possible** - Batch similar operations (6+ YouTube videos)
3. **Validate with git diff** - Always check changes before committing
4. **Remove duplicates intelligently** - Compare by video ID, not full URL
5. **Group by meaningful topics** - Analyze content to discover natural groupings
6. **Use emoji indicators** - Makes scanning references much easier
7. **Format as checkboxes** - Enables progress tracking in NotePlan
8. **Preserve user context** - Keep existing notes and annotations
9. **Single file focus** - Only modify the target file, nothing else
10. **Detailed commit messages** - Document what changed and why

### Future Enhancements

**Potential Improvements**:
1. Use `WebFetch` for article/blog metadata extraction
2. Implement `get_transcript` analysis for better video summaries
3. Add automatic tag generation based on content analysis
4. Support for PDF references with metadata extraction
5. Automatic archival of dead links to Archive.org
6. Cross-reference detection (same topics across different sources)
7. Automatic categorization using LLM topic classification
8. Generate summary statistics (e.g., "5 videos, 3 articles, 2 docs")

**Tool Wishlist**:
- `extract_article_metadata(url)` - Unified tool for web articles
- `detect_duplicates(urls_list)` - Smart duplicate detection
- `suggest_topics(content)` - AI-powered topic extraction
- `validate_url(url)` - Check if link is still active
