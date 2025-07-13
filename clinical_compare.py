import pandas as pd
import numpy as np

def values_are_equivalent(val1, val2):
    """
    Check if two values are equivalent, handling special cases:
    - Case-insensitive string comparison
    - Floating point precision (rounded to 6 decimal places)
    - Integer vs float formatting (23486.0 vs 23486)
    - String containment (TCGA-STAD vs STAD)
    """
    # If values are exactly the same, return True
    if val1 == val2:
        return True
    
    # Case-insensitive comparison
    if val1.lower() == val2.lower():
        return True
    
    # Try to convert to numbers for numeric comparison
    try:
        # Try converting both to float
        num1 = float(val1)
        num2 = float(val2)
        
        # Check if they're equal when rounded to 6 decimal places
        if abs(num1 - num2) < 1e-6:
            return True
            
    except (ValueError, TypeError):
        # If conversion fails, continue with string comparisons
        pass
    
    # Check string containment (case-insensitive)
    val1_lower = val1.lower()
    val2_lower = val2.lower()
    
    # Check if one string contains the other
    if val1_lower in val2_lower or val2_lower in val1_lower:
        return True
    
    return False

def compare_tsv_tables(file1_path, file2_path, output_file=None):
    """
    Compare two TSV tables based on submitter_id and report differences.
    
    Parameters:
    file1_path (str): Path to the first TSV file
    file2_path (str): Path to the second TSV file
    output_file (str, optional): Path to save the comparison results
    
    Returns:
    dict: Dictionary containing comparison results
    """
    
    # Read the TSV files
    try:
        df1 = pd.read_csv(file1_path, sep='\t', dtype=str)
        df2 = pd.read_csv(file2_path, sep='\t', dtype=str)
    except Exception as e:
        print(f"Error reading files: {e}")
        return None
    
    # Fill NaN values with empty strings for consistent comparison
    df1 = df1.fillna('')
    df2 = df2.fillna('')
    
    # Set submitter_id as index for easier comparison
    df1_indexed = df1.set_index('submitter_id')
    df2_indexed = df2.set_index('submitter_id')
    
    # Find common submitter_ids
    common_ids = set(df1_indexed.index) & set(df2_indexed.index)
    
    # Find unique submitter_ids in each table
    only_in_df1 = set(df1_indexed.index) - set(df2_indexed.index)
    only_in_df2 = set(df2_indexed.index) - set(df1_indexed.index)
    
    print(f"Total submitter_ids in table 1: {len(df1_indexed)}")
    print(f"Total submitter_ids in table 2: {len(df2_indexed)}")
    print(f"Common submitter_ids: {len(common_ids)}")
    print(f"Only in table 1: {len(only_in_df1)}")
    print(f"Only in table 2: {len(only_in_df2)}")
    print("-" * 50)
    
    # Initialize results dictionary
    results = {
        'total_common': len(common_ids),
        'only_in_table1': list(only_in_df1),
        'only_in_table2': list(only_in_df2),
        'differences': [],
        'identical_rows': 0
    }
    
    # Compare common submitter_ids
    differences_found = []
    
    for submitter_id in common_ids:
        row1 = df1_indexed.loc[submitter_id]
        row2 = df2_indexed.loc[submitter_id]
        
        # Compare each column
        row_differences = []
        
        # Get all columns except submitter_id (since we're using it as index) and 'group'
        columns_to_compare = [col for col in df1_indexed.columns if col in df2_indexed.columns and col != 'group']
        
        for col in columns_to_compare:
            val1 = str(row1[col]) if pd.notna(row1[col]) else ''
            val2 = str(row2[col]) if pd.notna(row2[col]) else ''
            
            # Custom comparison logic
            if not values_are_equivalent(val1, val2):
                row_differences.append({
                    'column': col,
                    'table1_value': val1,
                    'table2_value': val2
                })
        
        if row_differences:
            differences_found.append({
                'submitter_id': submitter_id,
                'differences': row_differences
            })
        else:
            results['identical_rows'] += 1
    
    results['differences'] = differences_found
    
    # Print summary
    print(f"Identical rows: {results['identical_rows']}")
    print(f"Rows with differences: {len(differences_found)}")
    
    # Print detailed differences
    if differences_found:
        print("\nDETAILED DIFFERENCES:")
        print("=" * 50)
        
        for diff in differences_found[:10]:  # Show first 10 differences
            print(f"\nSubmitter ID: {diff['submitter_id']}")
            for col_diff in diff['differences']:
                print(f"  Column '{col_diff['column']}':")
                print(f"    Table 1: '{col_diff['table1_value']}'")
                print(f"    Table 2: '{col_diff['table2_value']}'")
        
        if len(differences_found) > 10:
            print(f"\n... and {len(differences_found) - 10} more rows with differences")
    
    # Print rows only in one table
    if only_in_df1:
        print(f"\nSubmitter IDs only in table 1 (first 10): {list(only_in_df1)[:10]}")
    if only_in_df2:
        print(f"Submitter IDs only in table 2 (first 10): {list(only_in_df2)[:10]}")
    
    # Save results to file if specified
    if output_file:
        with open(output_file, 'w') as f:
            f.write("TSV COMPARISON RESULTS\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Total submitter_ids in table 1: {len(df1_indexed)}\n")
            f.write(f"Total submitter_ids in table 2: {len(df2_indexed)}\n")
            f.write(f"Common submitter_ids: {len(common_ids)}\n")
            f.write(f"Only in table 1: {len(only_in_df1)}\n")
            f.write(f"Only in table 2: {len(only_in_df2)}\n")
            f.write(f"Identical rows: {results['identical_rows']}\n")
            f.write(f"Rows with differences: {len(differences_found)}\n\n")
            
            if differences_found:
                f.write("DETAILED DIFFERENCES:\n")
                f.write("-" * 30 + "\n")
                for diff in differences_found:
                    f.write(f"\nSubmitter ID: {diff['submitter_id']}\n")
                    for col_diff in diff['differences']:
                        f.write(f"  Column '{col_diff['column']}':\n")
                        f.write(f"    Table 1: '{col_diff['table1_value']}'\n")
                        f.write(f"    Table 2: '{col_diff['table2_value']}'\n")
            
            if only_in_df1:
                f.write(f"\nSubmitter IDs only in table 1:\n{list(only_in_df1)}\n")
            if only_in_df2:
                f.write(f"\nSubmitter IDs only in table 2:\n{list(only_in_df2)}\n")
    
    return results

def create_difference_summary(results):
    """
    Create a summary of differences by column.
    """
    column_differences = {}
    
    for row_diff in results['differences']:
        for col_diff in row_diff['differences']:
            col_name = col_diff['column']
            if col_name not in column_differences:
                column_differences[col_name] = 0
            column_differences[col_name] += 1
    
    print("\nDIFFERENCES BY COLUMN:")
    print("-" * 30)
    for col, count in sorted(column_differences.items(), key=lambda x: x[1], reverse=True):
        print(f"{col}: {count} differences")
    
    return column_differences

# Example usage
if __name__ == "__main__":
    # Replace these with your actual file paths
    file1_path = "C:/Users/oriba/Downloads/clinical_data.tsv"
    file2_path = "C:/Users/oriba/Downloads/clinical_data_Luis.tsv"
    output_file = "C:/Users/oriba/Downloads/comparison_results.txt"
    
    # Compare the tables
    results = compare_tsv_tables(file1_path, file2_path, output_file)
    
    if results:
        # Create summary of differences by column
        column_summary = create_difference_summary(results)
        
        # You can also access specific results programmatically
        print(f"\nSUMMARY:")
        print(f"Total rows compared: {results['total_common']}")
        print(f"Identical rows: {results['identical_rows']}")
        print(f"Rows with differences: {len(results['differences'])}")
        
        # Example: Find all submitter_ids with differences in a specific column
        specific_column = "race"  # Change this to any column you're interested in
        ids_with_column_diff = []
        
        for row_diff in results['differences']:
            for col_diff in row_diff['differences']:
                if col_diff['column'] == specific_column:
                    ids_with_column_diff.append(row_diff['submitter_id'])
        
        if ids_with_column_diff:
            print(f"\nSubmitter IDs with differences in '{specific_column}' column:")
            print(ids_with_column_diff[:10])  # Show first 10

