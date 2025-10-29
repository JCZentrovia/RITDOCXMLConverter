<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>
  <xsl:param name="default-title" select="'Untitled Book'"/>
  <xsl:param name="stylesheet-href" select="'rittdoc.css'"/>

  <xsl:template match="/">
    <xsl:processing-instruction name="xml-stylesheet">
      <xsl:text>type="text/css" href="</xsl:text>
      <xsl:value-of select="$stylesheet-href"/>
      <xsl:text>"</xsl:text>
    </xsl:processing-instruction>
    <xsl:apply-templates select="node()"/>
  </xsl:template>

  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="/book">
    <xsl:copy>
      <xsl:apply-templates select="@*"/>
      <xsl:choose>
        <xsl:when test="bookinfo">
          <xsl:apply-templates select="bookinfo"/>
        </xsl:when>
        <xsl:otherwise>
          <bookinfo>
            <title>
              <xsl:choose>
                <xsl:when test="normalize-space(title)">
                  <xsl:value-of select="normalize-space(title[1])"/>
                </xsl:when>
                <xsl:otherwise>
                  <xsl:value-of select="$default-title"/>
                </xsl:otherwise>
              </xsl:choose>
            </title>
          </bookinfo>
        </xsl:otherwise>
      </xsl:choose>
      <xsl:apply-templates select="node()[not(self::bookinfo)]"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="info">
    <bookinfo>
      <xsl:apply-templates select="@*|node()"/>
    </bookinfo>
  </xsl:template>
</xsl:stylesheet>
