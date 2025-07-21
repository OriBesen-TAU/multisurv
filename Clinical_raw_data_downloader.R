library(TCGAbiolinks)
library(dplyr)
library(readr)
library(stringr)

# Step 1: Get all TCGA project IDs
project_ids <- stringr::str_subset(getGDCprojects()$project_id, 'TCGA')

# Step 2: Download data
data_list <- list()
all_columns <- character()
failed_projects <- character()

for (project_id in project_ids) {
  cat("Downloading:", project_id, "\n")
  
  tryCatch({
    clin <- GDCquery_clinic(project = project_id, type = "clinical")
    clin$disease <- project_id  # Tag with project ID
    all_columns <- union(all_columns, colnames(clin))  # Track all unique columns
    data_list[[project_id]] <- clin
  }, error = function(e) {
    cat("Skipping", project_id, "- Error:", conditionMessage(e), "\n")
    failed_projects <<- c(failed_projects, project_id)
  })
}

# Step 3: Add missing columns as NA (NaN)
for (project_id in names(data_list)) {
  clin <- data_list[[project_id]]
  missing_cols <- setdiff(all_columns, colnames(clin))
  if (length(missing_cols) > 0) {
    clin[missing_cols] <- NA  # Add NA columns
  }
  # Reorder columns to be consistent
  data_list[[project_id]] <- clin[, all_columns]
}

# Step 4: Merge everything
merged_data <- bind_rows(data_list)

# Step 5: Save to TSV
output_path <- "C:/Users/oriba/OneDrive/Documents/MultiOmics_data/clinical_data.tsv"
write_tsv(merged_data, output_path)

cat("✅ Clinical data saved to:", output_path, "\n")
if (length(failed_projects) > 0) {
  cat("⚠️ The following projects failed to download:\n", paste(failed_projects, collapse = ", "), "\n")
}
