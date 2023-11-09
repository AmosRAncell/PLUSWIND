################################################################################
# @author: Seongeun Jeong, LBNL
# @note: This scirpt downloads MERRA2 data from NASA GESDISC.
# NOTE on the download file list:
# 	An example of the file list is as follows:
# 		"http://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2/M2T1NXSLV.5.12.4/2021/01/MERRA2_400.tavg1_2d_slv_Nx.20210101.nc4.nc?U10M[0:23][253:282][157:185],V10M[0:23][253:282][157:185],U2M[0:23][253:282][157:185],V2M[0:23][253:282][157:185],U50M[0:23][253:282][157:185],V50M[0:23][253:282][157:185],DISPH[0:23][253:282][157:185],lat[253:282],time[0:23],lon[157:185]"
# 	The text (i.e., ".txt" file; see below in the code) file contains the list of files 
#		to download.
# 	Thus, each line in the text file contains the link to the file to download.
# 	In the below, each .txt file contains the whole data for a year
# 		as can been seen in the example file name. The user can change the structure of the file list.
# 	As can be seen in the example file link above, the file name should be associated 
#		with data version, the type, variable, temporal and spatial range of the data.
#	For details, refer to the MERRA2 documentation.
################################################################################

library (glue)
library (assertthat)
library (stringr)

################################################################################
# Options
################################################################################
Data_TYPE = 'hub_height_wspd' # some meaningful name for the data type.

#-------------------------------------------------------------------------------
# Years to download
#-------------------------------------------------------------------------------
YEARS = seq (2021, 2021) 

#-------------------------------------------------------------------------------
# Region to download (due to file size but CONUS can be donwloaded at once depending on the computational resources)
#	The region is specified by the latitude and longitude range, which 
#		are specified in the file list.
#-------------------------------------------------------------------------------
REGION = 'Northeast' 

#-------------------------------------------------------------------------------
# Data type
#-------------------------------------------------------------------------------
DTYPE = 'tavg1_2d_slv_Nx' #for WINDS

#===============================================================================
# Path
#===============================================================================
PATH_IN_LIST = "./"
PATH_OUT = './'

################################################################################
# # Iterate
# Example MERRA2 NetCDF file: MERRA2_300.tavg1_2d_slv_Nx.20040627.nc4.nc
################################################################################
for (ii in seq_along (YEARS)) {
	YEAR = YEARS [ii]
	
 	# ===============================================================================
 	# Get the list of files to download
	# Specifiy the file name text files as necessary.
	#	An example of the (download) file list file name is as follows:
 	# ===============================================================================
	FR = paste0(PATH_IN_LIST, 'MERRA_down_list_', REGION, '_', YEAR, '_', Data_TYPE, '.txt')	
	df = readLines (FR)

	NROW = length (df)
	
	# ===============================================================================
	# Iterate by file
	# ===============================================================================	
	for (jj in 1:NROW) {
		ff = df[jj]
		print (ff)
		
		fout.foo = strsplit (ff, '/')[[1]][9]
		fout = paste0(PATH_OUT, substring (fout.foo, 1, 42))
 
		# Provide the user email and password; required by NASA GESDISC.
		cmd.line = paste0('wget --user USER_EMAIL --password USER_PASSWORD --keep-session-cookies ',
  			ff, ' -O ', fout)
		system (cmd.line)
	}	
}
