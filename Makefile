TARGET=Issues.alfredworkflow

all: $(TARGET)

$(TARGET):
	pip install -qr requirements.txt -t src
	rm -r src/*.dist-info
	cd src && zip -qr ../$(TARGET) .

clean:
	rm -r $(TARGET) src/concurrent src/iso8601 src/requests src/requests_futures src/workflow
