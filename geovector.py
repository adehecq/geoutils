#!/usr/bin/env python
#coding=utf-8

#Python libraries
from osgeo import ogr, osr, gdal
import matplotlib.pyplot as pl
import numpy as np
import numbers
from copy import deepcopy
import mpl_toolkits.basemap.pyproj as pyproj
from matplotlib.patches import PathPatch
from matplotlib.path import Path
from matplotlib import cm
from matplotlib.collections import PatchCollection

#Personal libraries
import georaster as raster
import geometry as geo

"""
geovector.py

Classes to simplify reading geographic vector data and associated 
georeferencing information.

There are two classes available:

    SingleLayerVector    --  For loading datasets with only a single layer of 
                            data
    MultiLayerVector     --  For loading datasets that contain multiple layers 
                            of data (TO IMPLEMENT)

       The class works as a wrapper to the OGR API. A vector dataset can be loaded
into a class without needing to load the actual data, which is useful
for querying geo-referencing information without memory overheads.

The following attributes are available :

    class.ds    :   the OGR handle to the dataset, which provides access to 
                    all OGR functions, e.g. GetLayer, GetLayerCount...
                        More information on API:
                        http://gdal.org/python/osgeo.ogr.DataSource-class.html

    class.srs   :   an OGR Spatial Reference object representation of the 
                    dataset.
                        More information on API:
                        http://www.gdal.org/classOGRSpatialReference.html

    class.proj  :   a pyproj coordinate conversion function between the 
                    dataset coordinate system and lat/lon.

    class.extent :  tuple of the corners of the dataset in native coordinate
                    system, as (left,right,bottom,top).

    class.extent :  tuple of the corners of the dataset in native coordinate
                    system, as (left,right,bottom,top).

    class.layer : an OGR Layer object, see http://gdal.org/python/osgeo.ogr.Layer-class.html

    class.fields : an OGR field, i.e attributes to each feature. 
                   - fields.name contains the name of the fields
                   - fields.dtype contains the Numpy.dtype of the fields
                   - fields.value contains the value of the fields in form of a dictionary

Additionally, a number of instances are available in the class. 



Examples
--------

...


Created on Mon Feb 09 2015

@author: Amaury Dehecq (amaury.dehecq@univ-savoie.fr)
"""


# By default, GDAL/OGR does not raise exceptions - enable them
# See http://trac.osgeo.org/gdal/wiki/PythonGotchas
gdal.UseExceptions()
ogr.UseExceptions()


class Object(object):
    pass


class SingleLayerVector:

    def __init__(self,ds_filename,load_data=True,latlon=True,band=1):
        """ Construct object from vector file with a single layer. 
        
        Parameters:
            ds_filename : filename of the dataset to import

       The class works as a wrapper to the OGR API. A vector dataset can be loaded
into a class without needing to load the actual data, which is useful
for querying geo-referencing information without memory overheads.

The following attributes are available :

    class.ds    :   the OGR handle to the dataset, which provides access to 
                    all OGR functions, e.g. GetLayer, GetLayerCount...
                        More information on API:
                        http://gdal.org/python/osgeo.ogr.DataSource-class.html

    class.srs   :   an OGR Spatial Reference object representation of the 
                    dataset.
                        More information on API:
                        http://www.gdal.org/classOGRSpatialReference.html

    class.proj  :   a pyproj coordinate conversion function between the 
                    dataset coordinate system and lat/lon.

    class.extent :  tuple of the corners of the dataset in native coordinate
                    system, as (left,right,bottom,top).

    class.extent :  tuple of the corners of the dataset in native coordinate
                    system, as (left,right,bottom,top).

    class.layer : an OGR Layer object, see http://gdal.org/python/osgeo.ogr.Layer-class.html

    class.fields : an OGR field, i.e attributes to each feature. 
                   - fields.name contains the name of the fields
                   - fields.dtype contains the Numpy.dtype of the fields
                   - fields.value contains the value of the fields in form of a dictionary

Additionally, a number of instances are available in the class. 
        """

        self._load_ds(ds_filename)     



    def __del__(self):
        """ Close the gdal link to the dataset on object destruction """
        self.ds = None



    def _load_ds(self,ds_filename):
        """ Load link to data file and set up georeferencing """
        self.ds_file = ds_filename
        self.ds = ogr.Open(ds_filename)

        # Check to see if shapefile is found.
        if self.ds is None:
            print 'Could not open %s' % (ds_filename)

        #Get layer
        self.layer = self.ds.GetLayer()
        
        # For multiple layers
        # self.ds.layer = []
        # for i in xrange(self.ds.GetLayerCount()):
        # self.ds.layer.append(self.ds.GetLayerByIndex)

        # Get georeferencing infos
        self.srs = self.layer.GetSpatialRef()
        self.extent = self.layer.GetExtent()

        # Get layer fields name and type
        layerDefinition = self.layer.GetLayerDefn()
        
        fields = Object()
        fields.name = []
        fields.dtype = []
        fields._size = []
        for i in range(layerDefinition.GetFieldCount()):
            fields.name.append(layerDefinition.GetFieldDefn(i).GetName())
            fieldTypeCode = layerDefinition.GetFieldDefn(i).GetType()
            fields.dtype.append(layerDefinition.GetFieldDefn(i).GetFieldTypeName(fieldTypeCode))
            fields._size.append(layerDefinition.GetFieldDefn(i).GetWidth())

        # Convert types to Numpy dtypes
        # see http://www.gdal.org/ogr__core_8h.html#a787194bea637faf12d61643124a7c9fc
        # IntegerList, RealList, StringList, Integer64List not implemented yet.
        OGR2np = {'Integer':'i4','Real':'d','String':'S','Binary':'S','Date':'S','Time':'S','DateTime':'S','Integer64':'i8'}

        for k in xrange(len(fields.dtype)):
            dtype = OGR2np[fields.dtype[k]]
            if dtype=='S':
                dtype+=str(fields._size[k])
            fields.dtype[k] = dtype

        self.fields = fields
        
        self.proj = pyproj.Proj(self.srs.ExportToProj4())

        
    def read(self):
        """
        Load features and fields values defined in the vector file.
        Features filtered before are not read.
        """

        nFeat = self.layer.GetFeatureCount()
        
        #Initialize dictionnary containing fields data
        self.fields.values = {}
        for k in xrange(len(self.fields.name)):
            f = self.fields.name[k]
            dtype = self.fields.dtype[k]
            self.fields.values[f] = np.empty(nFeat,dtype=dtype)

        features = []
        for i in xrange(nFeat):
            #read each feature
            feat = self.layer.GetNextFeature()
            features.append(feat)

            #read each field associated to the feature
            for f in self.fields.name:
                self.fields.values[f][i] = feat.GetField(f)

        self.features = np.array(features)

    def FeatureCount():
        
        return self.layer.GetFeatureCount()


    def draw(self,indices='all',**kwargs):
        """
        Plot the geometries defined in the vector file
        Inputs :
        - indices : indices of the features to plot (Default is 'all')
        **kwargs : any optional argument accepted by the matplotlib.patches.PathPatch class, e.g.
            - edgecolor : mpl color spec, or None for default, or ‘none’ for no color
            - facecolor : mpl color spec, or None for default, or ‘none’ for no color
            - lw : linewidth, float or None for default
            - alpha : transparency, float or None
        """

        if not hasattr(self,'features'):
            print "You must run self.read() first"
            return 0

        if indices=='all':
            indices = range(len(self.features))
        elif isinstance(indices,numbers.Number):
            indices = [indices,] #create list if only one value

        for feat in self.features[indices]:
            sh = Shape(feat)
            sh.draw(**kwargs)

        ax = pl.gca()
        xmin, xmax,ymin,ymax = self.extent
        ax.set_xlim(xmin,xmax)
        ax.set_ylim(ymin,ymax)


    def draw_by_attr(self,attr,cmap=cm.jet,indices='all',**kwargs):
        """
        Plot the geometries defined in the vector file
        Inputs :
        - indices : indices of the features to plot (Default is 'all')
        **kwargs : any optional argument accepted by the matplotlib.patches.PathPatch class, e.g.
            - edgecolor : mpl color spec, or None for default, or ‘none’ for no color
            - facecolor : mpl color spec, or None for default, or ‘none’ for no color
            - lw : linewidth, float or None for default
            - alpha : transparency, float or None
        """

        if not hasattr(self,'features'):
            print "You must run self.read() first"
            return 0

        if indices=='all':
            indices = range(len(self.features))
        elif isinstance(indices,numbers.Number):
            indices = [indices,] #create list if only one value

        #create a collection of patches
        patches = []
        for k in indices:
            sh = Shape(self.features[k])
            patches.append(PathPatch(sh.path))

        p = PatchCollection(patches, cmap=cmap)
        p.set_array(np.array(self.fields.values[attr])) #set colors

        #Plot
        ax = pl.gca()
        ax.add_collection(p)
        cb = pl.colorbar(p)
        cb.set_label(attr)
        xmin, xmax,ymin,ymax = self.extent
        ax.set_xlim(xmin,xmax)
        ax.set_ylim(ymin,ymax)


    def crop(self,xmin,xmax,ymin,ymax):
        """
        Filter all features that are outside the rectangle defined by the corners xmin, xmax, ymin, ymax.
        Coordinates are in the same Reference System as the vector file.
        """
        # Create a ring linking the 4 corners
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(xmin, ymin)
        ring.AddPoint(xmin, ymax)
        ring.AddPoint(xmax, ymax)
        ring.AddPoint(xmax, ymin)
        ring.AddPoint(xmin, ymin)

        # Create polygon
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)

        #other method
#        wkt = "POLYGON ((%f %f, %f %f, %f %f, %f %f, %f %f))" %(xmin,ymin,xmin,ymax,xmax,ymax,xmax,ymin,xmin,ymin)
#        poly=ogr.CreateGeometryFromWkt(wkt)
        
        #Filter features outside the polygon
        self.layer.SetSpatialFilter(poly)
        
        #update attributes
        self.extent = poly.GetEnvelope()
    

    def crop2raster(self,rasterfile):
        """
        Filter all features that are outside the raster extent.
        """

        # Read raster extent
        img = raster.SingleBandRaster(rasterfile,load_data=False)
        xmin, xmax, ymin, ymax = img.extent

        # Reproject extent to vector geometry
        sourceSR = img.srs
        targetSR = self.srs
        transform = osr.CoordinateTransformation(sourceSR,targetSR)
        left, bottom = transform.TransformPoint(xmin,ymin)[:2]
        right, up = transform.TransformPoint(xmax,ymax)[:2]
        
        # Crop
        self.crop(left,right,bottom,up)


    def zonal_statistics(self,rasterfile,indices='all',nodata=None):
        """
        Compute statistics of the data in rasterfile for each feature in self.
        Inputs :
        - indices : indices of the features to compute (Default is 'all')
        """

        # Read raster coordinates
        img = raster.SingleBandRaster(rasterfile)
        X, Y = img.coordinates()

        # Coordinate transformation from vector to raster projection system
        coordTrans = osr.CoordinateTransformation(self.srs,img.srs)

        #Select only indices specified by user
        if indices=='all':
            indices = range(len(self.features))
        elif isinstance(indices,numbers.Number):
            indices = [indices,] #create list if only one value

        print "Loop on all features"
        median = []
        std = []
        count = []

        for feat in self.features[indices]:

            #Read feature geometry and reproject to raster projection
            sh = Shape(feat,load_data=False)
            sh.geom.Transform(coordTrans)
            sh.read()

            #Look only for points within the box of the feature
            xmin, xmax, ymin, ymax = sh.geom.GetEnvelope()
            inds = np.where((X>=xmin) & (X<=xmax) & (Y>=ymin) & (Y<=ymax))

            #Select data within the feature
            inside = geo.points_inside_polygon(X[inds],Y[inds],sh.vertices,skip_holes=False)
            inside = np.where(inside)
            inside_i = inds[0][inside]
            inside_j = inds[1][inside]

            data = img.r[inside_i,inside_j]

            #Filter no data values
            data = data[~np.isnan(data)]
            if nodata!=None:
                data = data[data!=nodata]

            #Compute statistics
            if len(data)>0:
                median.append(np.median(data))
                std.append(np.std(data))
                count.append(len(data))
            else:
                median.append(np.nan)
                std.append(np.nan)
                count.append(0)

        return np.array(median), np.array(std), np.array(count)

    def create_mask(self,raster):

        # Open the raster file
        x_res, y_res = raster.get_pixel_size()
        xsize, ysize = raster.r.shape
        x_min, x_max, y_min, y_max = raster.extent
    

        # Create memory target raster
        target_ds = gdal.GetDriverByName('MEM').Create('', xsize, ysize, 1, gdal.GDT_Byte)
        target_ds.SetGeoTransform((
                x_min, x_res, 0,
                y_max, 0, y_res,
                ))
    
        # Make the target raster have the same projection as the source raster
        target_ds.SetProjection(raster.srs.ExportToWkt())

        # Rasterize
        err = gdal.RasterizeLayer(target_ds, [1], self.layer,burn_values=[255])
        if err != 0:
            raise Exception("error rasterizing layer: %s" % err)

        # Read mask raster as arrays
        bandmask = target_ds.GetRasterBand(1)
        datamask = bandmask.ReadAsArray(0, 0, xsize, ysize)

        return datamask



class Shape():

        def __init__(self,feature,load_data=True):
            
            self.feature = feature
            self.geom = deepcopy(feature.GetGeometryRef()) #deepcopy otherwise the feature can be modified

            if load_data==True:
                self.read()


        def draw(self, **kwargs):
            """
            Draw the shape using the matplotlib.path.Path and matplotlib.patches.PathPatch classes
            **kwargs : any optional argument accepted by the matplotlib.patches.PathPatch class, e.g.
            - edgecolor : mpl color spec, or None for default, or ‘none’ for no color
            - facecolor : mpl color spec, or None for default, or ‘none’ for no color
            - lw : linewidth, float or None for default
            - alpha : transparency, float or None
            """
            
            #Create patch and get extent
            patch = PathPatch(self.path,**kwargs)
            xmin,xmax,ymin,ymax = self.extent

#            fig = pl.figure()
#            ax=fig.add_subplot(111)
            ax = pl.gca()
            ax.add_patch(patch)
            ax.set_xlim(xmin,xmax)
            ax.set_ylim(ymin,ymax)


        def read(self):
            """
            Read shape extent and vertices
            """

            self.extent = self.geom.GetEnvelope()

            vertices = []
            codes = []
            if self.geom.GetGeometryCount()>0:
                for i in xrange(self.geom.GetGeometryCount()):
                    poly = self.geom.GetGeometryRef(i)
                    for j in xrange(poly.GetPointCount()):
                        vertices.append([poly.GetX(j),poly.GetY(j)])
                        if j==0:
                            codes.append(Path.MOVETO)
                        elif j==poly.GetPointCount()-1:
                            codes.append(Path.CLOSEPOLY)
                        else:
                            codes.append(Path.LINETO)

                self.vertices = vertices   #list of vertices
                self.path = Path(vertices,codes)  #used for plotting
