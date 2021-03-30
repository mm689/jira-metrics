
# Analysis of Jira issues

## Overview
Generates `.csv` datasets and `.pdf` graphs relating to iterations, issues and the evolution of these in a single board on [Atlassian Jira](https://www.atlassian.com/software/jira).

## Requirements
- Docker
- A [Jira API key](https://id.atlassian.com/manage-profile/security/api-tokens)

## Usage
### 1. Create config file

JIRA Project and agile Board configuration is stored in `configs.txt`. You can produce this yourself, or your company may have a template to use. To help with writing this, `make get-boards` will retrieve the details of all boards you have access to.

Each line of `configs.txt` should be in the format `<project>/<board>`, where:
  - `project` is the JIRA internal name: it should be visible in your URL bar as `projectKey=<project>` when viewing the relevant board
  - `board` is the human-friendly board name: it should be visible in the [breadcrumbs](https://en.wikipedia.org/wiki/Breadcrumb_navigation#Websites) when viewing the board's page:
  ![image](https://user-images.githubusercontent.com/74246482/112482485-071b1100-8d70-11eb-8956-cf86e2f8dc10.png)

Example `configs.txt` file:
```
# comments work too!
PROJ1/Board One
PROJ2/Board Two
```

### 3. Get metrics for a single project
- Run `make`
  - This will rely on the **first** line of `configs.txt` only
  - You will be prompted for connection details if needed
- Documents will be opened automatically
  - After this, datasets can be found within the `augmented/` subdirectory within a folder named after your project
  - Graphs will be found in `graphs.pdf` under the same folder
  - Tabular data will be found in `table-team.html` under the same folder
- When you want to regenerate all data, for example after a new iteration, run `make regen`
  - This will again use configuration from the _first_ line of `configs.txt`

### For comparative data across projects
- Run `make compare-teams`
  - This will retrieve data for all boards in `config.txt`, and combine them into `all.iterations.csv`
  - The data in that `.csv` can be more easily viewed in your browser via `table.html`
  - Note: this only tracks the percentage _changes_ between metrics' values across iterations. `make summary-incl-raw` - run after the above - will include the raw values too (though in CSV format only, not HTML) - but be aware of the limitations of trying to compare raw data between teams!
- To regenerate any and all datasets (e.g. after teams complete an iteration), run `make regen-all`


#### Other commands

- `make regen-<project>` will (re)produce data for the given team without affecting any other data.
  - `<project>` can be a project name or number, e.g. `2` for the second configuration in `configs.txt`.
- `make summary` will ensure all cross-team statistics are up-to-date for projects whose data has already been downloaded. (For use only when developing the project.)
- `make zip` will produce `metrics.zip` containing some generated data.
- `make clean` will destroy all data for all projects
- `make cleanest` will clear out even your configuration.
