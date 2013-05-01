#!/usr/bin/python
from directories import Directory
import os
from os import path
import csv, codecs, cStringIO, re
        
filenames = {
    'codigos'    : 'elecciones_2013_codigos.csv', 
    'candidatos' : 'elecciones_2013_candidatos.csv', 
    'partidos'   : 'elecciones_2013_partidos.csv'
}

try:
  from lxml import etree
  print("running with lxml.etree")
except ImportError:
  try:
    # Python 2.5
    import xml.etree.cElementTree as etree
    print("running with cElementTree on Python 2.5+")
  except ImportError:
    try:
      # Python 2.5
      import xml.etree.ElementTree as etree
      print("running with ElementTree on Python 2.5+")
    except ImportError:
      try:
        # normal cElementTree install
        import cElementTree as etree
        print("running with cElementTree")
      except ImportError:
        try:
          # normal ElementTree install
          import elementtree.ElementTree as etree
          print("running with ElementTree")
        except ImportError:
          raise ImportError("Failed to import ElementTree from any known place, needed for the script to operate")

HTML_RESULTS_ID = ".//div[@id='resultDiv.21']"

class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)
            
class Scraper:
    """
    Escanea los HTMLs de los resultados y saca archivos CSV compilados
    """
    def __init__(self, directory,filenames = {}):
        self.directory = directory
        self.opcodes = ['codigos','partidos','candidatos']
        # Which CSV to generate
        self.options = {
            'codigos'    : self.do_scrape_codigos,
            'candidatos' : self.do_scrape_candidatos,
            'partidos'   : self.do_scrape_partidos
        }
        # Headers of the CSV files
        self.headers = {
            'codigos'       : ['estado', 'municipio', 'parroquia', 'centro', 'mesa', 'ubicacion'                        ],
            'candidatos'    : ['estado', 'municipio', 'parroquia', 'centro', 'mesa', 'candidato', 'votos', 'porcentaje' ],
            'partidos'      : ['estado', 'municipio', 'parroquia', 'centro', 'mesa', 'partido',   'votos', 'porcentaje' ]
        }
        self.headers_written = {
            'codigos'       : False,
            'candidatos'    : False,
            'partidos'      : False
        }
        # Filenames
        self.filenames = {
            'codigos'       : 'elecciones_codigos.csv',
            'candidatos'    : 'elecciones_candidatos.csv',
            'partidos'      : 'elecciones_partidos.csv'
        }
        # Length of the code for padding
        self.code_length = {
            6  : '0'*6,
            9  : '0'*3,
            12 : ''
        }
        
        if filenames != {}:
            try:
                new_filenames = filenames.viewkeys() ^ self.filenames.viewkeys()
                if new_filenames == set([]):
                    self.filenames.update(filenames)
                else:
                    raise KeyError
            except KeyError:
                raise Exception("Filename keys provided not valid, must be either "+(','.join(self.options.keys())))
    
    def do_scrape(self, options = []):
        if not self.valid_keys(options):
            raise KeyError('Opciones de recoleccion no validas: '+', '.join(options))

        directory = Directory(self.directory)
        if options == []:
            options = self.options.keys()
        
        self.clear_files()
        
        self.scrape_data(directory,options)
            
    def scrape_data(self, directory,options):
                
        files = directory.GetDictionary('files')
        dirs  = directory.GetDictionary('directories')
        
        for folder in dirs.values():
            print "Scraping "+folder.path
            self.scrape_data(folder,options) 
            print "Done scraping "+folder.path
            
        for result_data in files:
            filename = path.join(directory.path,result_data)
            result_code = result_data[4:-5]
            
            html_file = self.get_parsed_file(filename)
            root = html_file.getroot()
            results = root.findall(HTML_RESULTS_ID)
            
            if results == []:
                continue
            else:
                results = results[0]

            for option in options:
                self.options[option](result_code,root)

    def do_scrape_candidatos(self, result_code,root):
        candidatos  = []
        votes_per   = []
        votes       = []
        perc        = []
        
        results     = root.findall(HTML_RESULTS_ID)[0]
        resultados  = results.findall(".//tr/td/a[@href]")

        # Get the candidate name
        for candidato in resultados:
            candidatos.append(candidato.text)

        resultados = results.findall("./div/table/tr/td[@align]/span")
        
        # Get the votes and percentages
        for vote in resultados:
            vote = vote.text.replace('.','')
            vote = vote.replace(',','.')
            vote = vote.replace('%','')
            votes_per.append(vote)

        if candidatos == [] or votes_per == []:
            return

        votes = votes_per[0::2]
        perc  = votes_per[1::2]

        code = self.prepare_code(result_code)
        data = map(lambda x,y,z: code+[x,y,z], candidatos,votes,perc)
        
        #Tuple with votes and percentages per candidate.
        self.save_to_file('candidatos',data)
        
        return

    def do_scrape_partidos(self, result_code,root):
        data = []
        resultados = []
         
        # Now on a per-party basis
        partidos = root.findall(".//table[@class='n_s']")

        for candidato in partidos:
            for partido in candidato.findall(".//table/tr/td/span"):
                if partido.text == None:
                    result = partido[0].get('alt')
                else:
                    result = partido.text.replace('.','')
                    result = result.replace(',','.')
                    result = result.replace('%','')
                resultados.append(result)

        partido = resultados[0::3]
        votos   = resultados[1::3]
        percen  = resultados[2::3]

        code = self.prepare_code(result_code)
        data = map(lambda x,y,z: code+[x,y,z], partido,votos,percen)
        self.save_to_file('partidos',data)
        
        return

    def do_scrape_codigos(self, result_code,root):
        data = []
        
        codigos = root.findall(".//ul/li[@class='region-nav-item']/a")
        
        # Get the location codes
        if codigos != []:
            for codigo in codigos:
                data_code = re.search('reg_(?P<code>[0-9]+)\.html',codigo.get('href')).group('code')
                centre    = codigo.text.replace(',',' - ')
                temp_data = self.prepare_code(data_code)
                temp_data.append(centre)
                data.append(temp_data)

            self.save_to_file('codigos',data)
        
        return
        
    def valid_keys(self,options):
        if options == []:
            return True
        set_orig = set(self.options.keys())
        set_new  = set(options)
        
        return set_new.issubset(set_orig)
    
    def prepare_code(self,data_code):
        # We pad the code up to the maximum length to split it properly
        temp_code = data_code+(self.code_length[len(data_code)])
        
        # Estado - Municipio - Parroquia - Centro - Mesa - Nombre
        data = [ temp_code[:2], temp_code[2:4], temp_code[4:6], temp_code[6:9], temp_code[9:12] ]
        return data

    def get_parsed_file(self, filename):
        try:
            parser = etree.HTMLParser()
            html_file = etree.parse(filename,parser)
            return html_file
        except IOError,e:
            print 'get_parsed_file(): ',e
            raise Exception("Could not load "+filename+" for parsing")

    def save_to_file(self, filename_code, data):
        filename = self.filenames[filename_code]
        with open(filename, 'a+b') as csvfile:
            resultados = UnicodeWriter(csvfile, delimiter=',', quotechar='=', quoting=csv.QUOTE_MINIMAL)
            if not self.are_headers_written(filename_code):
                self.write_headers(filename_code)
            resultados.writerows(data)
            csvfile.close()

    def clear_files(self):
        for csv in self.filenames.values():
            if path.isfile(csv):
                os.remove(csv)

    def are_headers_written(self,filename_code):
        return self.headers_written[filename_code]

    def write_headers(self, filename_code):
        filename = self.filenames[filename_code]
        with open(filename, 'a+b') as csvfile:
            resultados = UnicodeWriter(csvfile, delimiter=',', quotechar='=', quoting=csv.QUOTE_MINIMAL)
            resultados.writerow(self.headers[filename_code])
            self.headers_written[filename_code] = True
            csvfile.close()

elecciones = Scraper('copiacne/resultado_presidencial_2013/',filenames)
elecciones.do_scrape()
print "Done!"