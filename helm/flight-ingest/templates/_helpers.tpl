{{/*
Expand the name of the chart.
*/}}
{{- define "flight-ingest.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "flight-ingest.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "flight-ingest.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "flight-ingest.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "flight-ingest.selectorLabels" -}}
app.kubernetes.io/name: {{ include "flight-ingest.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
