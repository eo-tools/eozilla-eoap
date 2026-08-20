#  Copyright (c) 2026- by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2-0.
library(jsonlite)
library(terra)
library(purrr)

args <- commandArgs(trailingOnly = TRUE)

local_catalog_dir <- args[1]
band_selection <- unlist(strsplit(args[2], ","))

local_catalog_path <- file.path(local_catalog_dir, "catalog.json")

local_catalog <- read_json(local_catalog_path)

local_item_links <- Filter(\(x) x$rel == "item", local_catalog$links)

local_items_paths <- map_chr(local_item_links, \(x) file.path(local_catalog_dir, x$href))

items <- map(local_items_paths, read_json)

find_asset_href <- function(item, common_name) {
  assets <- item$assets
  
  matches <- Filter(
    function(asset) {
      bands <- asset[["eo:bands"]]
      
      !is.null(bands) &&
        any(vapply(
          bands,
          function(band) {band[["common_name"]][[1]] == common_name},
          logical(1)
        )) &&
        grepl("\\.tif$", asset$href[[1]]) &&
        "data" %in% asset[["roles"]]
    },
    assets
  )
  
  if (length(matches) == 0) {
    stop("No asset found for common_name: ", common_name)
  }
  
  if (length(matches) > 1) {
    stop("Multiple assets found for common_name: ", common_name)
  }
  
  matches[[1]]$href
}

band_vector <- map(items, function(item, bands) {
  map(bands, \(x) find_asset_href(item, x))
}, bands = band_selection)

id_vector <- map_chr(items, \(x) unlist(x$id))

resampled_bands <- map_depth(band_vector, 2, function(band) {
  print(paste("Materializing", band))
  raster_band <- rast(band, vsi = TRUE)
  size_factor <- res(raster_band) / 10 # 10 is the lowest resolution for S2
  r <- disagg(raster_band, fact = size_factor)
  return(r)
})

walk2(resampled_bands, id_vector, function(bands, id, band_names) {
  stacked_raster <- rast(unlist(bands))
  names(stacked_raster) <- band_names
  writeRaster(stacked_raster, paste0(id, ".gtiff"), filetype = "GTiff")
}, band_names = band_selection)
