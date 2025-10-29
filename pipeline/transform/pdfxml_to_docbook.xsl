<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:param name="root-element" select="'book'"/>
  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

  <xsl:template match="/document">
    <xsl:element name="{$root-element}">
      <xsl:apply-templates select="block"/>
    </xsl:element>
  </xsl:template>

  <xsl:template match="block">
    <xsl:choose>
      <xsl:when test="@label='title'">
        <title><xsl:value-of select="."/></title>
      </xsl:when>
      <xsl:when test="@label='section'">
        <para role="section"><xsl:value-of select="."/></para>
      </xsl:when>
      <xsl:when test="@label='list_item'">
        <itemizedlist>
          <listitem><para><xsl:value-of select="."/></para></listitem>
        </itemizedlist>
      </xsl:when>
      <xsl:when test="@label='caption'">
        <caption><xsl:value-of select="."/></caption>
      </xsl:when>
      <xsl:when test="@label='footnote'">
        <footnote><para><xsl:value-of select="."/></para></footnote>
      </xsl:when>
      <xsl:otherwise>
        <para><xsl:value-of select="."/></para>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:stylesheet>
